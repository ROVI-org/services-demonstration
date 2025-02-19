#! /bin/bash
upload () {
  sleep 4.
  rovicli register cell ./tests/files/example-estimator.py ./tests/files/initial-asoh.json
  rovicli upload --report-freq 1000 cell ./tests/files/example-h5.h5 
  google-chrome http://localhost:8000/dashboard/cell/
}
upload &
uvicorn roviweb.api:app --workers 1

