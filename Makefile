.PHONY: install api web test build
install:            ## install backend + frontend deps
	pip install -r backend/requirements.txt
	cd frontend && npm install
api:                ## run FastAPI on :8000 (reload)
	cd backend && uvicorn risklab_api.main:app --reload --port 8000
web:                ## run Next.js on :3000
	cd frontend && npm run dev
test:               ## backend tests (engine + API + content lint)
	python -m pytest backend/tests -q
build:              ## production build of the frontend
	cd frontend && npm run build
