run:
	uvicorn app:app --reload

test:
	pytest -q

eval:
	python evaluate.py