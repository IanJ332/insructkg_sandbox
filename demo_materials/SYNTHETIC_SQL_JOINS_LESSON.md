# SQL JOINs, NULL Semantics, and Missing Records

> **SYNTHETIC COURSE MATERIAL — LOCAL RESEARCH DEMONSTRATION**
>
> This original lesson is a synthetic SIIP demonstration fixture. It was not authored or
> approved by Professor Abdussalam Alawini and is not presented as institutional course material.

## Business scenario

Northstar Services wants a staffing report for every department, including departments that do
not yet have employees. Its small relational schema is:

```sql
CREATE TABLE departments (
    department_id INTEGER PRIMARY KEY,
    department_name TEXT NOT NULL
);

CREATE TABLE employees (
    employee_id INTEGER PRIMARY KEY,
    employee_name TEXT NOT NULL,
    department_id INTEGER,
    FOREIGN KEY (department_id) REFERENCES departments(department_id)
);
```

Assume `departments` contains Sales, Engineering, and Research, while no employee has yet been
assigned to Research.

## INNER JOIN: return matching pairs

An `INNER JOIN` returns only rows for which its join predicate finds a matching row on both sides.

```sql
SELECT d.department_name, e.employee_name
FROM departments AS d
INNER JOIN employees AS e
    ON e.department_id = d.department_id;
```

This is appropriate for a report of current employee assignments. It omits Research because
Research has no matching employee record. Using this query for the all-departments report is a
common mistake: the syntax is valid, but the result silently loses the missing match.

## LEFT OUTER JOIN: preserve the left table

A `LEFT OUTER JOIN` (often written `LEFT JOIN`) retains every row from the left table. When the
join predicate finds no right-side record, SQL fills the selected right-side columns with `NULL`.

```sql
SELECT d.department_name, e.employee_name
FROM departments AS d
LEFT OUTER JOIN employees AS e
    ON e.department_id = d.department_id;
```

Now Research remains in the report. Its `employee_name` is `NULL`, meaning there is no matching
employee value for that row; it is not an empty string or the number zero.

## Finding missing matching records

To list only departments without employees, preserve departments with a left join and then test a
non-nullable employee key for `NULL`:

```sql
SELECT d.department_id, d.department_name
FROM departments AS d
LEFT JOIN employees AS e
    ON e.department_id = d.department_id
WHERE e.employee_id IS NULL;
```

Use `IS NULL`, not `= NULL`. SQL's three-valued logic treats ordinary comparisons with `NULL` as
unknown, so `e.employee_id = NULL` does not select the missing matches.

## Check your reasoning

Before choosing a join, ask: "Must rows without a match remain visible?" Use an inner join when
only matching pairs belong in the result. Put the table whose rows must all survive on the left of
a left outer join, and handle unmatched right-side values explicitly with `IS NULL`, `IS NOT NULL`,
or a carefully chosen display function such as `COALESCE`.
