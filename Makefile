VERSION := $(shell python3 -c "import crm; print(crm.__version__)")
IMAGE ?= leandrocode/crmtech

.PHONY: help run test e2e check-db build push clean

help: ## Muestra esta ayuda
	@grep -E '^[a-z0-9-]+:.*## ' $(MAKEFILE_LIST) | sed -E 's/:.*## /|/' | awk -F'|' '{ printf "  make %-9s %s\n", $$1, $$2 }'

run: ## Arranca el servidor local (SQLite en ./data)
	python3 -m crm

test: ## Pruebas unitarias y de API (rápidas, sin navegador)
	python3 -m unittest discover -s tests -t . -v

e2e: ## Prueba de navegador (necesita Playwright, ver tests/e2e/run.sh)
	bash tests/e2e/run.sh

check-db: ## Verifica conexión, migraciones y escritura de DATABASE_URL
	python3 -m crm check-db

build: ## Arma la imagen con la versión del paquete (IMAGE:VERSION)
	docker build --build-arg VERSION=$(VERSION) -t $(IMAGE):$(VERSION) .

push: build ## Sube la imagen a Docker Hub
	docker push $(IMAGE):$(VERSION)

clean: ## Borra archivos temporales de Python
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
