import csv
import filecmp
import re
import shutil
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
LOGS_DIR = BASE_DIR                      # folder holding the machine .txt logs
FLAGS_CSV = BASE_DIR / "concrete_validation_flags.csv"
FLAGGED_DIR = BASE_DIR / "flagged_files"  # copies of flagged logs 

CALENDAR_FILE = Path(
    "/home/jessicamaldonado/OneDrive/Calendars/Calendar_materials.xlsx"
)
SHEET_NAME = "Table_concrete_BM"
AGES = {
    1: "D1",
    3: "D3",
    7: "D7",
    14: "D14",
    28: "D28",
}

CHECK_FROM = date(2026, 3, 10)
YEAR_COLUMN = "data_id_with_year"


TEST_KINDS = {
    "compression": {"pattern": r"Compression \w", "expected_samples": 5},
    "flexural": {"pattern": r"Flexural \w", "expected_samples": None},
}

ERROR_CODES = {
    "1": "Label error",
    "1.1": "Week error",
    "1.2": "Formulation error",
    "1.3": "Mix design error",
    "1.4": "Initial error",
    "1.5": "Sample error",
    "2": "Age error",
}
LABEL_PARTS = [  # (part name, error code if wrong)
    ("week", "1.1"),
    ("formulation", "1.2"),
    ("mix", "1.3"),
    ("initial", "1.4"),
    ("sample", "1.5"),
]
PART_LABELS = {
    "week": "Week",
    "formulation": "Formulation",
    "mix": "Mix design",
    "initial": "Initial",
    "sample": "Sample",
}
LABEL_PATTERN = re.compile(
    r"^(?P<week>\d+)-(?P<formulation>[A-Z])(?P<mix>[A-Z0-9]+?)(?P<initial>[A-Z])(?P<sample>\d+)$"
)
VALID_FORMULATIONS = {"C", "G"}

MIN_MATCHING_PARTS = 3

FLAG_HEADER = [
    "Flagged at", "Source file", "Concrete ID", "Age", "Test date",
    "Error code", "Error type", "Problem", "Copied to",
]


class Schedule(dict):

    def __init__(self):
        super().__init__()
        self.years = {}


def casting_year(day, age):
    try:
        return (day - timedelta(days=int(age))).year
    except (OverflowError, ValueError, TypeError):
        return None


def _year_from_cell(value):
    match = re.search(r"(\d{4})\s*$", str(value if value is not None else ""))
    if match and 2000 <= int(match.group(1)) <= 2100:
        return int(match.group(1))
    return None


def load_schedule(calendar_file=CALENDAR_FILE):
    #Return a Schedule
    calendar_file = Path(calendar_file)

    if calendar_file.suffix.lower() == ".csv":
        with calendar_file.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        # The supplied csv contains DD/MM/YYYY dates.
        parse_date = lambda value: datetime.strptime(str(value).strip(), "%d/%m/%Y").date()
    else:
        # The original production system uses its Excel workbook.
        table = pd.read_excel(calendar_file, sheet_name=SHEET_NAME)
        rows = table.to_dict("records")

        def parse_date(value):
            return pd.to_datetime(value, dayfirst=True).date()

    required = {"ID-BM", *AGES.values()}
    if not rows:
        raise ValueError("Concrete calendar is empty")
    missing = required - set(rows[0])
    if missing:
        raise ValueError(f"Concrete calendar is missing columns: {sorted(missing)}")

    schedule = Schedule()
    for row in rows:
        label = str(row.get("ID-BM") or "").strip().upper()
        if not label or label == "NAN":
            continue
        row_year = _year_from_cell(row.get(YEAR_COLUMN))
        for age, column in AGES.items():
            value = row.get(column)
            if value is None or str(value).strip().lower() in {"", "nan", "nat"}:
                continue
            try:
                day = parse_date(value)
            except (ValueError, TypeError) as exc:
                raise ValueError(f"Invalid {column} date for {label}: {value!r}") from exc
            schedule.setdefault((day, label), set()).add(age)
            schedule.years[(day, label)] = row_year or casting_year(day, age)

    return schedule


def classify_test(test_type):
    #Return 'compression', 'flexural' or None (not a concrete strength test).
    for kind, settings in TEST_KINDS.items():
        if re.search(settings["pattern"], test_type):
            return kind
    return None


def split_label(label):
    #Split e.g. 41-CBTC6D1 into week/formulation/mix/initial/sample, or None.
    match = LABEL_PATTERN.match(str(label or "").strip().upper())
    return match.groupdict() if match else None


_index_cache = {"schedule": None, "size": -1, "by_day": {}, "by_label": {}, "by_label_year": {}}


def _index(schedule):
    #Lookups by test day, by label, and by (label, casting year)
    cache = _index_cache
    if cache["schedule"] is not schedule or cache["size"] != len(schedule):
        by_day, by_label, by_label_year = {}, {}, {}
        years = getattr(schedule, "years", {})
        for (day, label), ages in schedule.items():
            by_day.setdefault(day, {})[label] = ages
            by_label.setdefault(label, {})[day] = ages
            year = years.get((day, label)) or casting_year(day, min(ages))
            by_label_year.setdefault((label, year), {})[day] = ages
        cache.update(
            schedule=schedule, size=len(schedule),
            by_day=by_day, by_label=by_label, by_label_year=by_label_year,
        )
    return cache["by_day"], cache["by_label"], cache["by_label_year"]


def closest_labels(parts, pool):
    """Calendar labels in pool sharing the most parts with the log's label."""
    best_score, best = 0, []
    for candidate in sorted(pool):
        cand_parts = split_label(candidate)
        if cand_parts is None:
            continue
        score = sum(parts[key] == cand_parts[key] for key, _ in LABEL_PARTS)
        if score > best_score:
            best_score, best = score, [(candidate, cand_parts)]
        elif score == best_score and score:
            best.append((candidate, cand_parts))
    return best_score, best


def diagnose_concrete(label, age, test_date, schedule):
    problems = []
    label = str(label or "").strip().upper()

    if isinstance(test_date, datetime):
        day = test_date.date()
    elif isinstance(test_date, date):
        day = test_date
    else:
        try:
            day = datetime.strptime(str(test_date).strip(), "%d/%m/%Y").date()
        except ValueError:
            day = None

    # Before the calendar existed there is nothing to check against.
    if day is not None and CHECK_FROM and day < CHECK_FROM:
        return []

    if day is None:
        problems.append(("", "No usable test date"))
    if not label:
        problems.append(("1", "Concrete ID is missing"))

    raw_age = str(age).strip() if age is not None else ""
    try:
        number_age = int(raw_age)
    except ValueError:
        number_age = None
        problems.append(("2", "Test age is missing or not a whole number"))

    if day is None or not label:
        return problems

    by_day, by_label, by_label_year = _index(schedule)
    due_today = by_day.get(day, {})

    # Week numbers restart every January, so a label only counts as "in the
    # calendar" for the year it was cast in (test date minus age). If the age is
    # unusable, any year will do.
    cast_year = casting_year(day, number_age) if number_age is not None else None

    # A label that is due on this date can only have an age problem.
    if label in due_today:
        expected_ages = due_today[label]
        if number_age is not None and number_age not in expected_ages:
            ages_text = "/".join(str(a) for a in sorted(expected_ages))
            problems.append((
                "2", f"Age is {number_age} days, but {label} is due at {ages_text} days on {day:%d/%m/%Y}"
            ))
        return problems

    label_dates = by_label_year.get((label, cast_year)) if cast_year else by_label.get(label)
    if label_dates:
        due = "; ".join(
            f"{a} days on {d:%d/%m/%Y}"
            for d, ages in sorted(label_dates.items())
            for a in sorted(ages)
        )
        problems.append((
            "2", f"{label} is not due for testing on {day:%d/%m/%Y} (it is due at {due})"
        ))
        return problems

    where = f" for casting year {cast_year}" if cast_year else ""
    parts = split_label(label)
    if parts is None:
        problems.append((
            "1", f"{label} is not in the WEEK-FORMULATION/MIX/INITIAL/SAMPLE format (e.g. 41-CBTC6D1)"
        ))
        return problems

    # Compare with what is due on this date (preferring labels due at this age).
    pool = {lab: ages for lab, ages in due_today.items()
            if number_age is None or number_age in ages} or due_today
    score, best = closest_labels(parts, pool)
    names = ", ".join(lab for lab, _ in best[:3])

    if score >= MIN_MATCHING_PARTS:
        for key, code in LABEL_PARTS:
            expected = sorted({cand[key] for _, cand in best})
            if parts[key] not in expected:
                problems.append((
                    code,
                    f"{PART_LABELS[key]} in {label} is {parts[key]}, calendar has "
                    f"{'/'.join(expected)} (closest calendar label: {names})",
                ))
        if number_age is not None and not any(number_age in pool[lab] for lab, _ in best):
            problems.append((
                "2", f"Age is {number_age} days, but {names} is not due at that age on {day:%d/%m/%Y}"
            ))

    if parts["formulation"] not in VALID_FORMULATIONS and not any(c == "1.2" for c, _ in problems):
        problems.append((
            "1.2", f"Formulation in {label} is {parts['formulation']}, expected C or G"
        ))

    if not any(code.startswith("1") for code, _ in problems):
        if score >= MIN_MATCHING_PARTS:
            problems.append(("1", f"{label} is not in the calendar{where} (closest: {names})"))
        else:
            problems.append((
                "1", f"{label} is not in the calendar{where} and no close match is due on {day:%d/%m/%Y}"
            ))
    return problems


def check_concrete(label, age, test_date, schedule):
    """Return plain-English issues (with their error code) for a concrete test."""
    return [
        f"Error {code} ({ERROR_CODES[code]}): {text}" if code else text
        for code, text in diagnose_concrete(label, age, test_date, schedule)
    ]


def check_sample_counts(counts, schedule, today=None):
    #Compare valid logs
    
    today = today or date.today()
    issues = []
    for kind, settings in TEST_KINDS.items():
        expected = settings["expected_samples"]
        if expected is None:
            continue
        for (day, label), ages in sorted(schedule.items()):
            if day > today or (CHECK_FROM and day < CHECK_FROM):
                continue
            for age in sorted(ages):
                found = counts.get((kind, day, label, age), 0)
                if found == expected:
                    continue
                if found < expected and day == today:
                    continue
                issues.append((
                    label, age, day,
                    f"Found {found} valid {kind} logs for {label} at {age} days "
                    f"on {day:%d/%m/%Y}, expected {expected}",
                ))
    return issues


def copy_to_flagged(path):
    #Copy a flagged log into flagged_files; the original is left where it is.
    try:
        FLAGGED_DIR.mkdir(parents=True, exist_ok=True)
        n = 0
        while True:
            name = path.name if n == 0 else f"{path.stem}_{n}{path.suffix}"
            target = FLAGGED_DIR / name
            if not target.exists():
                shutil.copy2(path, target)
                return str(target)
            if filecmp.cmp(path, target, shallow=False):
                return str(target)
            n += 1
    except OSError as exc:
        return f"NOT COPIED: {exc}"


def _dedupe_key(row):
    # Everything except the time of the run and where the copy is.
    return tuple(str(row[i]) for i in (1, 2, 3, 4, 5, 7))


def write_flags(flags, output_file):
    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    seen = set()
    if output_file.exists():
        with output_file.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.reader(stream))
        if rows and rows[0] == FLAG_HEADER:
            seen = {_dedupe_key(row) for row in rows[1:] if len(row) == len(FLAG_HEADER)}
        else:
            # Older report with different columns: keep it, start a fresh one.
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file.rename(output_file.with_name(f"{output_file.stem}_old_{stamp}{output_file.suffix}"))

    new_file = not output_file.exists()
    written = []
    with output_file.open("a", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        if new_file:
            writer.writerow(FLAG_HEADER)
        for row in flags:
            key = _dedupe_key(row)
            if key in seen:
                continue
            seen.add(key)
            writer.writerow(row)
            written.append(row)
    return written


def machine_value(lines, index):
    if index >= len(lines) or "=" not in lines[index]:
        raise ValueError(f"Missing machine field at line {index + 1}")
    return lines[index].split("=", 1)[1].strip().strip('"').strip()


def log_date_from_name(name):
    """Test date from a machine log filename like 02_11_2026_09_36_45.592_Last test.txt."""
    match = re.match(r"^(\d{2})_(\d{2})_(\d{4})_", name)
    if not match:
        return None
    day, month, year = map(int, match.groups())
    try:
        return date(year, month, day)
    except ValueError:
        return None


def check_local_logs(logs_dir=LOGS_DIR):

    schedule = load_schedule(CALENDAR_FILE)
    logs_dir = Path(logs_dir)
    flagged = {}   # path -> [(label, age, test day, code, problem)]
    counts = {}    # (kind, test day, label, age) -> number of valid logs
    checked = skipped = before_start = 0

    for path in sorted(logs_dir.glob("*.txt")):
        if not path.is_file():
            continue

        # Logs from before the calendar existed are not looked at at all.
        test_day = log_date_from_name(path.name)
        if test_day and CHECK_FROM and test_day < CHECK_FROM:
            before_start += 1
            continue

        label = age = ""
        kind = None
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            test_type = machine_value(lines, 1)   # parameter 0 - test name
            kind = classify_test(test_type)
            if kind is None:
                skipped += 1
                continue
            if test_day is None:
                raise ValueError("Unrecognised machine log filename/date")

            label = machine_value(lines, 17)      # parameter 16: e.g. 41-CBTC6D1
            age = machine_value(lines, 9)         # parameter 8: age in days
            problems = diagnose_concrete(label, age, test_day, schedule)
        except (OSError, ValueError, IndexError) as exc:
            problems = [("", f"Could not read concrete test values: {exc}")]

        checked += 1
        if problems:
            flagged[path] = [(label, age, test_day or "", code, text) for code, text in problems]
        else:
            key = (kind, test_day, label.strip().upper(), int(age))
            counts[key] = counts.get(key, 0) + 1

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    rows = []
    for path, issues in flagged.items():
        copied_to = copy_to_flagged(path)
        for label, age, test_day, code, problem in issues:
            rows.append((
                now, str(path), label, age, test_day,
                code, ERROR_CODES.get(code, ""), problem, copied_to,
            ))

    count_issues = check_sample_counts(counts, schedule)
    for label, age, day, problem in count_issues:
        rows.append((now, "", label, age, day, "", "", problem, ""))

    new_rows = write_flags(rows, FLAGS_CSV)
    for row in new_rows:
        if row[1]:
            shown = f"Error {row[5]} ({row[6]}): {row[7]}" if row[5] else row[7]
            print(f"FLAGGED: {Path(row[1]).name} - {shown}", flush=True)
        else:
            print(f"COUNT: {row[7]}", flush=True)

    print(
        f"Concrete logs checked: {checked}; ignored (before {CHECK_FROM:%d/%m/%Y}): {before_start}; "
        f"other logs skipped: {skipped}; flagged logs: {len(flagged)}; "
        f"new problems reported: {len(new_rows)}; count problems: {len(count_issues)}",
        flush=True,
    )
    print(f"Report: {FLAGS_CSV}", flush=True)
    print(f"Copies of flagged logs: {FLAGGED_DIR}", flush=True)


def watch_local_logs(logs_dir=LOGS_DIR):
    """Keep the terminal running, checking after new logs finish writing."""
    logs_dir = Path(logs_dir)

    def snapshot():
        result = {}
        for path in logs_dir.glob("*.txt"):
            try:
                stat = path.stat()
                result[path.name] = (stat.st_size, stat.st_mtime_ns)
            except OSError:
                continue
        # Recheck if the calendar is updated too.
        try:
            result["__calendar__"] = CALENDAR_FILE.stat().st_mtime_ns
        except OSError:
            result["__calendar__"] = None
        return result

    print(f"Watching: {logs_dir}", flush=True)
    print(f"Calendar: {CALENDAR_FILE.name}", flush=True)
    print("Checking every 5 seconds. Press Ctrl+C to stop.\n", flush=True)
    last_checked = None

    try:
        while True:
            current = snapshot()
            if current != last_checked:
                time.sleep(2)
                if snapshot() == current:
                    try:
                        check_local_logs(logs_dir)
                    except (OSError, ValueError) as exc:
                        print(f"Validation could not run: {exc}", flush=True)
                    else:
                        last_checked = current
            time.sleep(5)
    except KeyboardInterrupt:
        print("\nWatcher stopped.")


if __name__ == "__main__":
    args = sys.argv[1:]
    folder = LOGS_DIR
    if "--logs-dir" in args:
        folder = Path(args[args.index("--logs-dir") + 1])
    if "--watch-local" in args:
        watch_local_logs(folder)
    else:
        check_local_logs(folder)
