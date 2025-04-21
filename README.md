# SONetwork
Self Organizing Network

![alt text](image.png)
  
- создание виртуального окружения
```bash
python3 -m venv env
```
  
- активация виртуального окружения
```bash
source env/bin/activate
```
  
- установка модулей питона
```bash
pip3 install -r requirements-dev.txt
```
  
- запуск всех тестов с подробным выводом
```bash
python3 -m pytest -v
```
  
запуск конкретного теста test_name
```bash
python3 -m pytest -v tests/test_*.py::<test_name>
```
  
- покрытие в html
```bash
python3 -m pytest -v --cov=src --cov-report=html
```
  
- покрытие в терминале
```bash
python3 -m pytest -v --cov=src --cov-report=term-missing
```
  
- запуск симуляции с автоматической генерацией сети
```bash
python3 main.py
```
  
- запуск с загрузкой сети в состоянии, сохранённом в конфиге (.json)
```bash
python3 main.py
```
  
- запуск с подменой терминала, которым будет управлять мнимый пользователь
```bash
USER_SIMULATION=1 python3 main.py
```
