import csv
import filecmp
import re
import shutil
import sys
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
LOGS_DIR = BASE_DIR                      # folder holding the machine .txt logs
FLAGS_CSV = BASE_DIR / "mortar_validation_flags.csv"
FLAGGED_DIR = BASE_DIR / "flagged_files"  # copies of flagged logs

CALENDAR_FILE = Path(
    "/home/jessicamaldonado/OneDrive/Calendars/Calendar_materials.xlsx"
)
SHEET_NAME = "Table_mortar"

AGES = {
    1: "D1",
    3: "D3",
    7: "D7",
    14: "D14",
    28: "D28",
}

# Normal TM mortar

NORMAL_AGES = {3, 7, 14, 28}

# set at each of 7, 14 and 28 days. They never have D1 or D3.
MM_AGES = {7, 14, 28}

# The normal mortar calendar does not have a D3 test for mixes cast on these days.
SKIP_D3_WEEKDAYS = {"Wednesday", "Thursday"}

# MM mix designs
MM_MIX_PREFIX = "MM"

PARAM_AGE = 8
PARAM_LABEL = 25
PARAM_TEST_TYPE = 28


# Mortar testing uses three flexural tests and six compression tests per
TEST_KINDS = {
    "compression": {"code": "C", "expected_samples": 6},
    "flexural": {"code": "F", "expected_samples": 3},
}

# Only check count completeness on/after this day.  None = all calendar dates.
COUNT_CHECK_FROM = None

ERROR_CODES = {
    "1": "Label error",
    "1.1": "Week error",
    "1.2": "Formulation error",
    "1.3": "Mix design error",
    "1.4": "Initial error",
    "1.5": "Sample error",
    "2": "Age error",
    "3": "Type error",
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
    "Flagged at", "Source file", "Mortar ID", "Age", "Test date",
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


def parse_date_from_filename(file_path):
  stem = Path(file_path).stem
  match = re.match(r"^(\d{2}_\d{2}_\d{4})", stem)
  if not match:
    raise ValueError(f"Filename does not start with DD_MM_YYYY: {stem!r}")
  return datetime.strptime(match.group(1), "%d_%m_%Y").date()



def load_schedule(calendar_file=CALENDAR_FILE):
    calendar_file = Path(calendar_file)

    if calendar_file.suffix.lower() == ".csv":
        with calendar_file.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
    else:
        table = pd.read_excel(calendar_file, sheet_name=SHEET_NAME)
        rows = table.to_dict("records")

    if not rows:
        raise ValueError("Mortar calendar is empty")

    required = {"ID-Mortar", *AGES.values(), "Day"}
    missing = required - set(rows[0])
    if missing:
        raise ValueError(
            f"Mortar calendar is missing columns: {sorted(missing)}"
        )

    schedule = Schedule()
    for row in rows:
        label = str(row.get("ID-Mortar") or "").strip().upper()
        if not label or label == "NAN":
            continue

        mix_day_raw = row.get("Day")
        try:
            mix_day = parse_date_from_filename(mix_day_raw)
        except ValueError:
            mix_day = None

        allowed_ages = allowed_ages_for_label(label, mix_day)

        for age, column in AGES.items():
            if age not in allowed_ages:
                continue

            value = row.get(column)
            if value is None or str(value).strip().lower() in {"", "nan", "nat", "none"}:
                continue

            try:
                test_day = parse_date_from_filename(value)
            except ValueError as exc:
                raise ValueError(
                    f"Invalid {column} date for {label}: {value!r}"
                ) from exc

            schedule.setdefault((test_day, label), set()).add(age)

            row_year = _year_from_cell(row.get("data_id_with_year"))
            schedule.years[(test_day, label)] = (
                row_year or casting_year(test_day, age)
            )

    return schedule


def classify_test(test_type):
    value = str(test_type or "").strip().upper()
    if value == TEST_KINDS["compression"]["code"]:
        return "compression"
    if value == TEST_KINDS["flexural"]["code"]:
        return "flexural"
    return None


def split_label(label):
    # Split the mortar label into week/formulation/mix/initial/sample.
    match = LABEL_PATTERN.match(str(label or "").strip().upper())
    return match.groupdict() if match else None


def is_mm_mix(label):
    """Return True when the label uses an MM mix design."""
    parts = split_label(label)
    if not parts:
        return False

    mix = str(parts.get("mix", "")).strip().upper()
    return mix.startswith(MM_MIX_PREFIX)


def allowed_ages_for_label(label, mix_day=None):
    # Return the ages that should exist for a mortar label.

    if is_mm_mix(label):
        return set(MM_AGES)

    allowed = set(NORMAL_AGES)

    if mix_day is not None and mix_day.strftime("%A") in SKIP_D3_WEEKDAYS:
        allowed.discard(3)

    return allowed


_index_cache = {
    "schedule": None,
    "size": -1,
    "by_day": {},
    "by_label": {},
    "by_label_year": {},
}


def _index(schedule):
    #Lookups by test day, by label, and by (label, casting year).
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
            schedule=schedule,
            size=len(schedule),
            by_day=by_day,
            by_label=by_label,
            by_label_year=by_label_year,
        )

    return cache["by_day"], cache["by_label"], cache["by_label_year"]


def closest_labels(parts, pool):
    best_score, best = 0, []
    for candidate in sorted(pool):
        cand_parts = split_label(candidate)
        if cand_parts is None:
            continue
        score = sum(
            parts[key] == cand_parts[key]
            for key, _ in LABEL_PARTS
        )
        if score > best_score:
            best_score, best = score, [(candidate, cand_parts)]
        elif score == best_score and score:
            best.append((candidate, cand_parts))
    return best_score, best


def _normalise_test_date(test_date):
    if isinstance(test_date, datetime):
        return test_date.date()
    if isinstance(test_date, date):
        return test_date
    try:
        return datetime.strptime(
            str(test_date).strip(), "%d/%m/%Y"
        ).date()
    except ValueError:
        parsed = pd.to_datetime(str(test_date).strip(), dayfirst=True, errors="coerce")
        return None if pd.isna(parsed) else parsed.date()


def diagnose_mortar(label, age, test_date, schedule, test_type=None):
    problems = []
    label = str(label or "").strip().upper()
    day = _normalise_test_date(test_date)

    # F/C selector must be exactly C or F.
    if test_type is not None:
        normalised_type = str(test_type).strip().upper()
        if not normalised_type:
            problems.append(("3", "Test type is missing; expected C or F"))
        elif normalised_type not in {"C", "F"}:
            problems.append(
                ("3", f"Test type is {normalised_type!r}; expected C or F")
            )

    if day is None:
        problems.append(("", "No usable test date"))
    if not label:
        problems.append(("1", "Mortar ID is missing"))

    raw_age = str(age).strip() if age is not None else ""
    try:
        number_age = int(float(raw_age))
    except (ValueError, OverflowError):
        number_age = None
        problems.append(("2", "Test age is missing or not a whole number"))

    if day is None or not label:
        return problems

    by_day, by_label, by_label_year = _index(schedule)
    due_today = by_day.get(day, {})

    cast_year = casting_year(day, number_age) if number_age is not None else None

    # A label that exists in the calendar must be tested on the correct day.
    if label in by_label:
        expected_ages = due_today.get(label)
        if expected_ages is None:
            label_dates = (
                by_label_year.get((label, cast_year), {})
                if cast_year is not None
                else by_label.get(label, {})
            )
            if not label_dates:
                label_dates = by_label.get(label, {})

            due = "; ".join(
                f"{a} days on {d:%d/%m/%Y}"
                for d, ages in sorted(label_dates.items())
                for a in sorted(ages)
            )
            problems.append(
                (
                    "2",
                    f"{label} is not due for testing on {day:%d/%m/%Y}"
                    + (f" (it is due at {due})" if due else ""),
                )
            )
        elif number_age is not None and number_age not in expected_ages:
            ages_text = "/".join(str(a) for a in sorted(expected_ages))
            problems.append(
                (
                    "2",
                    f"Age is {number_age} days, but {label} is due at "
                    f"{ages_text} days on {day:%d/%m/%Y}",
                )
            )
        return problems

    # Label is not in the calendar at all. Try to diagnose which part of the label changed.
    parts = split_label(label)
    if parts is None:
        problems.append(
            (
                "1",
                f"{label} is not in the WEEK-FORMULATION/MIX/INITIAL/SAMPLE "
            )
        )
        return problems

    pool = {
        lab: ages
        for lab, ages in due_today.items()
        if number_age is None or number_age in ages
    } or due_today

    score, best = closest_labels(parts, pool)
    names = ", ".join(lab for lab, _ in best[:3])

    if score >= MIN_MATCHING_PARTS:
        for key, code in LABEL_PARTS:
            expected = sorted({cand[key] for _, cand in best})
            if parts[key] not in expected:
                problems.append(
                    (
                        code,
                        f"{PART_LABELS[key]} in {label} is {parts[key]}, "
                        f"calendar has {'/'.join(expected)} "
                        f"(closest calendar label: {names})",
                    )
                )

        if number_age is not None and not any(
            number_age in pool[lab] for lab, _ in best
        ):
            problems.append(
                (
                    "2",
                    f"Age is {number_age} days, but {names} is not due at "
                    f"that age on {day:%d/%m/%Y}",
                )
            )

    if parts["formulation"] not in VALID_FORMULATIONS and not any(
        code == "1.2" for code, _ in problems
    ):
        problems.append(
            (
                "1.2",
                f"Formulation in {label} is {parts['formulation']}, expected C or G",
            )
        )

    if not any(code.startswith("1") for code, _ in problems):
        if score >= MIN_MATCHING_PARTS:
            problems.append(
                ("1", f"{label} is not in the calendar (closest: {names})")
            )
        else:
            problems.append(
                (
                    "1",
                    f"{label} is not in the calendar and no close match is due "
                    f"on {day:%d/%m/%Y}",
                )
            )

    return problems


def check_mortar(label, age, test_date, schedule, test_type=None):
    return [
        (
            f"Error {code} ({ERROR_CODES[code]}): {text}"
            if code
            else text
        )
        for code, text in diagnose_mortar(
            label, age, test_date, schedule, test_type
        )
    ]


def check_sample_counts(counts, schedule, today=None):
    #Check 6 C logs and 3 F logs for every completed label/age/date set.
    today = today or date.today()
    issues = []

    for kind, settings in TEST_KINDS.items():
        expected = settings["expected_samples"]
        for (day, label), ages in sorted(schedule.items()):
            if day > today or (COUNT_CHECK_FROM and day < COUNT_CHECK_FROM):
                continue

            for age in sorted(ages):
                found = counts.get((kind, day, label, age), 0)
                if found == expected:
                    continue

                # Do not call a currently-running day's incomplete set an error.
                if found < expected and day == today:
                    continue

                test_name = "compression" if kind == "compression" else "flexural"
                issues.append(
                    (
                        label,
                        age,
                        day,
                        f"Found {found} valid {test_name} logs for {label} at {age} days "
                        f"on {day:%d/%m/%Y}, expected {expected}",
                    )
                )

    return issues


def copy_to_flagged(path):
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
            seen = {
                _dedupe_key(row)
                for row in rows[1:]
                if len(row) == len(FLAG_HEADER)
            }
        else:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file.rename(
                output_file.with_name(
                    f"{output_file.stem}_old_{stamp}{output_file.suffix}"
                )
            )

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
    match = re.match(r"^(\d{2})_(\d{2})_(\d{4})_", name)
    if not match:
        return None
    day, month, year = map(int, match.groups())
    try:
        return date(year, month, day)
    except ValueError:
        return None


def get_test_date_from_log(filename):
    return log_date_from_name(filename)


def read_mortar_fields(path):
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()

    params = {}
    for line_number, line in enumerate(lines):
        match = re.match(r"^\s*(\d+)\s*=\s*(.*?)\s*$", line)
        if not match:
            continue
        value = match.group(2).strip()
        if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
            value = value[1:-1].strip()
        params[int(match.group(1))] = value

    # The numbered machine parameters are normally identical to their
    def value_for(parameter, line_index):
        if parameter in params:
            return params[parameter]
        return machine_value(lines, line_index)

    label = value_for(PARAM_LABEL, PARAM_LABEL)
    age = value_for(PARAM_AGE, PARAM_AGE)
    test_type = value_for(PARAM_TEST_TYPE, PARAM_TEST_TYPE)
    test_date = get_test_date_from_log(path.name)

    if test_date is None:
        # Final fallback in case the date field was not parsed into params.
        test_date = log_date_from_name(path.name)

    return label, age, test_type, test_date


def find_problems(path, schedule):
    """Validate a single mortar log; useful for the standalone local tester too."""
    path = Path(path)
    label = age = test_type = ""
    test_date = None

    try:
        label, age, test_type, test_date = read_mortar_fields(path)
    except (OSError, ValueError, IndexError) as exc:
        return [f"Could not read mortar test values: {exc}"]

    return check_mortar(label, age, test_date, schedule, test_type)


def check_local_logs(logs_dir=LOGS_DIR):
    """Validate mortar logs before downstream processing."""
    schedule = load_schedule(CALENDAR_FILE)
    logs_dir = Path(logs_dir)
    flagged = {} 
    counts = {}   
    checked = skipped = 0

    for path in sorted(logs_dir.glob("*.txt")):
        if not path.is_file():
            continue

        label = age = test_type = ""
        test_day = None
        kind = None

        try:
            label, age, test_type, test_day = read_mortar_fields(path)

            kind = classify_test(test_type)
            problems = diagnose_mortar(
                label,
                age,
                test_day,
                schedule,
                test_type,
            )
        except (OSError, ValueError, IndexError) as exc:
            problems = [("", f"Could not read mortar test values: {exc}")]

        checked += 1

        if problems:
            flagged[path] = [
                (label, age, test_day or "", code, text)
                for code, text in problems
            ]
        else:
            if kind is None:
                # Defensive fallback; diagnose_mortar should already have caught it.
                flagged[path] = [
                    (
                        label,
                        age,
                        test_day or "",
                        "3",
                        f"Test type is {test_type!r}; expected C or F",
                    )
                ]
            else:
                key = (
                    kind,
                    test_day,
                    label.strip().upper(),
                    int(float(age)),
                )
                counts[key] = counts.get(key, 0) + 1

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    rows = []

    for path, issues in flagged.items():
        copied_to = copy_to_flagged(path)
        for label, age, test_day, code, problem in issues:
            name = ERROR_CODES.get(code, "")
            rows.append(
                (
                    now,
                    str(path),
                    label,
                    age,
                    test_day,
                    code,
                    name,
                    problem,
                    copied_to,
                )
            )
            shown = (
                f"Error {code} ({name}): {problem}"
                if code
                else problem
            )
            print(
                f"FLAGGED: {path.name} - {shown}",
                flush=True,
            )

    count_issues = check_sample_counts(counts, schedule)
    for label, age, day, problem in count_issues:
        rows.append((now, "", label, age, day, "", "", problem, ""))
        print(f"COUNT: {problem}", flush=True)

    new_rows = write_flags(rows, FLAGS_CSV)

    print(
        f"Mortar logs checked: {checked}; other logs skipped: {skipped}; "
        f"flagged logs: {len(flagged)}; new problems reported: {len(new_rows)}; "
        f"count problems: {len(count_issues)}",
        flush=True,
    )
    print(f"Report: {FLAGS_CSV}", flush=True)
    print(f"Copies of flagged logs: {FLAGGED_DIR}", flush=True)


def watch_local_logs(logs_dir=LOGS_DIR):
    logs_dir = Path(logs_dir)

    def snapshot():
        result = {}
        for path in logs_dir.glob("*.txt"):
            try:
                stat = path.stat()
                result[path.name] = (stat.st_size, stat.st_mtime_ns)
            except OSError:
                continue

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
                        print(
                            f"Validation could not run: {exc}",
                            flush=True,
                        )
                    else:
                        last_checked = current
            time.sleep(5)
    except KeyboardInterrupt:
        print("\nWatcher stopped.")


def main():
    args = sys.argv[1:]
    folder = LOGS_DIR

    if "--logs-dir" in args:
        index = args.index("--logs-dir")
        if index + 1 >= len(args):
            raise SystemExit("--logs-dir requires a folder path")
        folder = Path(args[index + 1])

    if "--watch-local" in args:
        watch_local_logs(folder)
    else:
        check_local_logs(folder)


if __name__ == "__main__":
    main()
