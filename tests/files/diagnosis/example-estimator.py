"""Example estimator from:
https://github.com/ROVI-org/model-to-prognosis/blob/parallel-estimation/2_prepare-for-asoh-estimation.ipynb"""
from pathlib import Path

import numpy as np
from battdat.data import CellDataset
from moirae.extractors.ecm import OCVExtractor, MaxCapacityExtractor
from moirae.models.base import HealthVariable, GeneralContainer
from moirae.models.ecm import EquivalentCircuitModel, ECMInput, ECMASOH, ECMTransientVector
from moirae.estimators.online.joint import JointEstimator
from moirae.estimators.offline.loss import MeanSquaredLoss
from moirae.estimators.offline.scipy import ScipyMinimizer

# Load the initial ASOH
initial_asoh = ECMASOH.model_validate_json(Path('initial-asoh.json').read_text())
initial_transients = ECMTransientVector.from_asoh(initial_asoh)


def perform_offline_estimation(
        dataset: CellDataset,
        init_asoh: ECMASOH = initial_asoh,
        init_state: GeneralContainer = initial_transients,
        extract_q_t: bool = False,
        extract_ocv: bool = False,
        offline_fits: list[str] = ()
) -> tuple[HealthVariable, GeneralContainer]:
    """Use extraction and offline estimation to fit health parameters

    Args:
        dataset: Dataset with raw data to use for fitting
        init_asoh: Initial guess for ASOH
        init_state: Initial guess for transient state at first timestep
        extract_q_t: Whether to use the capacity extractor
        extract_ocv: Whether to use the OCV extractor
        offline_fits: List of variables to fit with offline estimation (fitting via SciPy mimimize)
    Returns:
        - Improved guess for ASOH
        - Improved guess for initial transient state
    """

    # Make an output copy
    asoh = init_asoh.model_copy(deep=True)
    state = init_state.model_copy(deep=True)

    # Perform cap extraction
    if extract_q_t:
        asoh.q_t = MaxCapacityExtractor().extract(dataset)

    # Perform OCV extraction
    if extract_ocv:
        asoh.ocv = OCVExtractor(asoh.q_t, soc_points=16, interpolation_style='linear').extract(dataset)

    # Perform state estimation
    if len(offline_fits) > 0:
        asoh.mark_all_fixed()
        for p in offline_fits:
            asoh.mark_updatable(p)

        loss = MeanSquaredLoss(
            cell_model=EquivalentCircuitModel(),
            transient_state=state,
            asoh=asoh,
            observations=dataset
        )
        scipy = ScipyMinimizer(loss, method='Nelder-Mead')
        state, asoh, result = scipy.estimate()
    return asoh, state


def make_estimator(init_asoh: ECMASOH, init_transients: ECMTransientVector) -> JointEstimator:
    """Generate an online estimator provided an initial health measurement

    Args:
        init_asoh: Initial ASOH estimate
        init_transients: Initial transient state
    Returns:
        Estimator
    """
    # Adjust reference OCV to include points outside the initial domain
    init_asoh.ocv(0.5)  # Initializes the interpolation points
    soc_pinpoints = [-0.1] + init_asoh.ocv.ocv_ref.soc_pinpoints.flatten().tolist() + [1.1]
    base_vals = [0.] + init_asoh.ocv.ocv_ref.base_values.flatten().tolist() + [6.5]
    init_asoh.ocv.ocv_ref.base_values = np.array([base_vals])
    init_asoh.ocv.ocv_ref.soc_pinpoints = np.array(soc_pinpoints)
    init_asoh.ocv.ocv_ref.interpolation_style = 'linear'

    # Make it so the capacity will be estimated
    init_asoh.mark_updatable('q_t.base_values')
    init_asoh.mark_updatable('r0.base_values')

    # Uncertainties for the parameters
    # For A-SOH, assume 2*standard_dev is 0.5% of the value of the parameter
    asoh_covariance = [(2.5e-03 * init_asoh.q_t.base_values.item()) ** 2]  # +/- std_dev^2 Qt
    asoh_covariance += ((2.5e-03 * init_asoh.r0.base_values.flatten()) ** 2).tolist()  # +/- std_dev^2 of R0
    asoh_covariance = np.diag(asoh_covariance)

    # For the transients, assume SOC is a uniform random variable in [0,1], and hysteresis has 2*std_dev of 1 mV
    tran_covariance = np.diag([1 / 100, 2.5e-07])

    # Make the noise terms
    #  Logic from: https://github.com/ROVI-org/auto-soh/blob/main/notebooks/demonstrate_joint_ukf.ipynb
    voltage_err = 1.0e-03  # mV voltage error
    noise_sensor = ((voltage_err / 2) ** 2) * np.eye(1)
    noise_asoh = 1.0e-10 * np.eye(asoh_covariance.shape[0])
    noise_tran = 1.0e-08 * np.eye(2)

    return JointEstimator.initialize_unscented_kalman_filter(
        cell_model=EquivalentCircuitModel(),
        initial_asoh=init_asoh.model_copy(deep=True),
        initial_inputs=ECMInput(
            time=0,
            current=0,
        ),
        initial_transients=init_transients,
        covariance_asoh=asoh_covariance,
        covariance_transient=tran_covariance,
        transient_covariance_process_noise=noise_tran,
        asoh_covariance_process_noise=noise_asoh,
        covariance_sensor_noise=noise_sensor
    )
