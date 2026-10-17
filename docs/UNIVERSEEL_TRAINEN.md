# Universele Windows-training

Pak de ZIP van branch `feature/model-v0.11.0` uit en dubbelklik op `train_en_test_auto.bat`.

Het programma controleert via Windows PowerShell/CIM de CPU, het aantal logische processors, RAM en GPU. Bij ontbrekende systeeminformatie gebruikt het een veilige CPU-standaard. Het maximum is 16 workers en op kleinere systemen worden minder workers gekozen. Het hardwareprofiel staat in `training_reports/hardware_profile.json`.

De volgorde is: hardwarecontrole, Python-tests, korte optimalisatie, uitgebreide optimalisatie met een doelbudget van vier uur. De GPU wordt uitsluitend gedetecteerd; de training blijft CPU-gebaseerd. Het productiemodel wordt niet gewijzigd.

Python 3.11+ is nodig. De training gebruikt alleen historische gegevens uit de uitgepakte repository. De checkpoint- en rapportbestanden staan in `training_reports/`. Een lopende berekening kan de streeftijd overschrijden.
