# Makefile для проекта SONetwork

VENV_DIR = env
PYTHON = $(VENV_DIR)/bin/python3
PIP = $(VENV_DIR)/bin/pip3
PYTEST = $(PYTHON) -m pytest
OUT_BASE = out
DOXYGEN = doxygen

# Цвета для подсветки
RED    = \033[0;31m
GREEN  = \033[0;32m
YELLOW = \033[1;33m
CYAN   = \033[0;36m
NC     = \033[0m # Сброс цвета

# Создание виртуального окружения
venv: ## Создать виртуальное окружение
	python3 -m venv $(VENV_DIR)

# Установка зависимостей
install: venv ## Установить зависимости из requirements-dev.txt
	$(PIP) install -r requirements-dev.txt --quiet

# Запуск всех тестов с подробным выводом
test: install ## Запустить все тесты с подробным выводом
	$(PYTEST) -v

# Запуск конкретного теста
# Использование: make test-single test_name=<имя_теста>
test-single: install ## Запустить конкретный тест (указать test_name и module_name)
ifndef test_name
	$(error Пожалуйста, укажите test_name, например: make test-single module_name=my_module test_name=my_test)
endif
	$(PYTEST) -v tests/test_$(module_name).py::$(test_name)

# Покрытие кода с отчетом в терминале
coverage-term: install ## Запустить тесты с покрытием и отчетом в терминале
	$(PYTEST) -v --cov=src --cov-report=term-missing

# Покрытие кода с отчетом в html
coverage-html: install ## Запустить тесты с покрытием и отчетом в HTML
	$(PYTEST) -v --cov=src --cov-report=html

# Запуск симуляции с автоматической генерацией сети
run: install ## Запустить симуляцию (main.py)
	$(PYTHON) main.py

# Запуск с загрузкой сети из конфига
# Использование: make run-load config=<путь_к_файлу.json>
run-load: install ## Запустить с загрузкой сети из config (указать config)
ifndef config
	$(error Пожалуйста, укажите config, например: make run-load config=config.json)
endif
	$(PYTHON) main.py -l $(config)

# Запуск с подменой терминала мнимым пользователем
run-user: install ## Запустить с подменой терминала мнимым пользователем
	$(PYTHON) src/user.py | $(PYTHON) main.py

# Генерация документации
docs: ## Сгенерировать документацию с помощью doxygen
	$(DOXYGEN)

# Очистка виртуального окружения и отчетов
clean-all: ## Очистить виртуальное окружение и все отчеты
	rm -rf `find . -name __pycache__`
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf docs
	rm -rf .coverage
	rm -rf $(OUT_BASE)
	rm -rf $(VENV_DIR)

# Цель help — выводит список команд с описаниями и подсветкой
help:
	@printf "$(CYAN)Доступные команды Makefile для проекта SONetwork:$(NC)\n"
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
	awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-15s$(NC) %s\n", $$1, $$2}'

.PHONY: venv install test test-single coverage-term coverage-html run run-load run-user docs clean-all help
