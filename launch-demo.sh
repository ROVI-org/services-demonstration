#! /bin/bash
upload () {
  sleep 4.
  path=./tests/files/example-h5.h5
  name=`rovicli register $path`
  echo "Registered dataset as $name"
  rovicli diagnosis register $name ./tests/files/example-estimator.py ./tests/files/initial-asoh.json
  rovicli prognosis register $name \
    ./tests/files/prognosis/example-forecaster.py \
    "SELECT test_time,q_t__base_values FROM \$TABLE_NAME\$ ORDER BY test_time DESC LIMIT 10000" \
    ./tests/files/prognosis/*.pkl
  rovicli upload --report-freq 1000 $name ./tests/files/example-h5.h5
}
start_chrome () {
  sleep 5
  google-chrome http://localhost:8000/
}

rm duck.db
upload &
start_chrome &
uvicorn roviweb.api:app --workers 1
