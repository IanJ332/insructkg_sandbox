CREATE TABLE Employees(employee_id INTEGER PRIMARY KEY, name TEXT NOT NULL, department_id INTEGER);
CREATE TABLE Departments(department_id INTEGER PRIMARY KEY, department_name TEXT NOT NULL);
INSERT INTO Employees VALUES (1,'Alice',10),(2,'Bob',20),(3,'Carol',NULL),(4,'David',10);
INSERT INTO Departments VALUES (10,'Engineering'),(20,'Sales'),(30,'Research');
INSERT INTO Employees VALUES (5,'Erin',30),(6,'Frank',NULL),(7,'Gina',99);
INSERT INTO Departments VALUES (40,'Operations');
