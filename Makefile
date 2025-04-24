# Makefile для проекта SONetwork

VENV_DIR = env
PYTHON = $(VENV_DIR)/bin/python3
PIP = $(VENV_DIR)/bin/pip3
PYTEST = $(PYTHON) -m pytest
OUT_BASE = out
DOXYGEN = doxygen

# Создание виртуального окружения
venv:
	python3 -m venv $(VENV_DIR)

# Установка зависимостей
install: venv
	$(PIP) install -r requirements-dev.txt --quiet

# Запуск всех тестов с подробным выводом
test: install
	$(PYTEST) -v

# Запуск конкретного теста
# Использование: make test-single test_name=<имя_теста>
test-single: install
ifndef test_name
	$(error Пожалуйста, укажите test_name, например: make test-single module_name=my_module test_name=my_test)
endif
	$(PYTEST) -v tests/test_$(module_name).py::$(test_name)

# Покрытие кода с отчетом в терминале
coverage-term: install
	$(PYTEST) -v --cov=src --cov-report=term-missing

# Покрытие кода с отчетом в html
coverage-html: install
	$(PYTEST) -v --cov=src --cov-report=html

# Запуск симуляции с автоматической генерацией сети
run: install
	$(PYTHON) main.py

# Запуск с загрузкой сети из конфига
# Использование: make run-load config=<путь_к_файлу.json>
run-load: install
ifndef config
	$(error Пожалуйста, укажите config, например: make run-load config=config.json)
endif
	$(PYTHON) main.py -l $(config)

# Запуск с подменой терминала мнимым пользователем
run-user: install
	$(PYTHON) src/user.py | $(PYTHON) main.py

# Генерация документации
docs:
	$(DOXYGEN)

# Очистка виртуального окружения и отчетов
clean-all:
	rm -rf `find . -name __pycache__`
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf docs
	rm -rf .coverage
	rm -rf $(OUT_BASE)
	rm -rf $(VENV_DIR)

.PHONY: venv install test test-single coverage-term coverage-html run run-load run-user docs clean-all
