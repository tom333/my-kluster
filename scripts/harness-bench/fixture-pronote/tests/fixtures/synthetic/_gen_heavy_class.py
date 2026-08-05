#!/usr/bin/env python3
"""Generator for tests/fixtures/synthetic/heavy_class.json (D-16, TIME-03, GRADE-03).

Run: python tests/fixtures/synthetic/_gen_heavy_class.py
Committed output: tests/fixtures/synthetic/heavy_class.json
Parameters: ~126 lessons (3wk x 6d x 7), 100 grades, 30 informations.
Anchor: today = date(2026, 5, 26) so J-7 = May 19, J+14 = June 9.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

# Import our own models so the JSON shape stays in sync with Snapshot.to_dict().
# Must run from repo root: python tests/fixtures/synthetic/_gen_heavy_class.py
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from custom_components.ha_pronote.api.models import Grade, Information, Lesson, Snapshot

_TZ = ZoneInfo("Pacific/Noumea")

SUBJECTS = [
    "Mathématiques",
    "Français",
    "Histoire-Géographie",
    "EPS",
    "Physique-Chimie",
    "Anglais",
]

TEACHERS = [
    "M. Dupont",
    "Mme Martin",
    "M. Bernard",
    "Mme Leroy",
    "M. Moreau",
    "Mme Simon",
]

CLASSROOMS = ["B204", "S102", "GYM", "A301", "B105", "EXT"]

LESSON_TIMES = [
    (7, 30, 8, 25),
    (8, 30, 9, 25),
    (9, 30, 10, 25),
    (10, 40, 11, 35),
    (12, 0, 12, 55),
    (13, 0, 13, 55),
    (14, 0, 14, 55),
    (15, 0, 15, 55),
]

LONG_EXCERPT_BASE = (
    "La réunion parents-professeurs aura lieu le jeudi 12 juin 2026 de 17h00 à 20h00 "
    "dans la salle des fêtes de l'établissement. Tous les parents sont invités à venir "
    "rencontrer les enseignants de leur enfant. Merci de vous munir du carnet de "
    "correspondance. En cas d'empêchement, veuillez contacter le secrétariat avant le 10 juin. "
    "Chaque entretien durera environ 5 minutes. La liste des enseignants présents sera "
    "affichée à l'entrée. Pour les parents d'élèves de terminale, des informations "
    "supplémentaires concernant l'orientation post-bac seront disponibles en salle 201."
)


def _make_lesson(
    d: date,
    slot: tuple[int, int, int, int],
    subject: str,
    teacher: str,
    classroom: str,
    canceled: bool = False,
) -> Lesson:
    h_s, m_s, h_e, m_e = slot
    start = datetime(d.year, d.month, d.day, h_s, m_s, tzinfo=_TZ)
    end = datetime(d.year, d.month, d.day, h_e, m_e, tzinfo=_TZ)
    return Lesson(
        date=d,
        start=start,
        end=end,
        subject=subject,
        teacher=teacher,
        classroom=classroom,
        canceled=canceled,
        status="Cours annulé" if canceled else "",
    )


def generate() -> dict:
    today = date(2026, 5, 26)
    lessons: list[Lesson] = []

    # 3 weeks: J-7 to J+14 (21 days). Skip weekends.
    for day_offset in range(-7, 15):
        d = today + timedelta(days=day_offset)
        if d.weekday() >= 5:  # skip Saturday (5) and Sunday (6)
            continue
        # 7 lessons per teaching day
        for i, slot in enumerate(LESSON_TIMES):
            subj = SUBJECTS[i % len(SUBJECTS)]
            teacher = TEACHERS[i % len(TEACHERS)]
            classroom = CLASSROOMS[i % len(CLASSROOMS)]
            # Cancel 1 lesson per week on Tuesday for realism
            canceled = d.weekday() == 1 and i == 2
            lessons.append(_make_lesson(d, slot, subj, teacher, classroom, canceled))

    # 100 grades across 6 subjects
    grades: list[Grade] = []
    grade_values = [str(v) for v in range(8, 20)]  # 8 to 19
    for i in range(100):
        subj = SUBJECTS[i % len(SUBJECTS)]
        val = grade_values[i % len(grade_values)]
        class_avg = str(int(val) - 2) if int(val) >= 10 else str(int(val) + 1)
        g_date = today - timedelta(days=(i % 21))  # spread over J-21..today
        grades.append(
            Grade(
                subject=subj,
                value=val,
                out_of="20",
                coefficient=str(1 + (i % 3)),
                date=g_date,
                class_average=class_avg,
                class_min=str(max(4, int(val) - 6)),
                class_max=str(min(20, int(val) + 3)),
                comment="Excellent travail" if int(val) >= 17 else "",
            )
        )

    # 30 informations with 500-char excerpts (stress the 500-char cap)
    infos: list[Information] = []
    for i in range(30):
        # Spread over April-May 2026 so day-of-month stays valid (don't subtract i from 26).
        published = datetime(2026, 5, 26, 8, 0, tzinfo=_TZ) - timedelta(days=i)
        excerpt = (LONG_EXCERPT_BASE * 3)[:500]  # exactly 500 chars
        # Teacher full names already include the title — use them as-is.
        sender = "Direction" if i % 3 == 0 else TEACHERS[i % len(TEACHERS)]
        infos.append(
            Information(
                info_id=f"info-{i:04d}",
                title=f"Information #{i + 1}",
                sender=sender,
                date=published,
                excerpt=excerpt,
                read=(i % 4 == 0),  # 25% read
            )
        )

    snap = Snapshot(
        today=today,
        school_tz="Pacific/Noumea",
        lessons=lessons,
        grades=grades,
        information=infos,
        overall_average="14,50",
        period_name="Trimestre 2",
    )
    return snap.to_dict()


if __name__ == "__main__":
    data = generate()
    out = Path(__file__).parent / "heavy_class.json"
    out.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    lesson_count = len(data["lessons"])
    grade_count = len(data["grades"])
    info_count = len(data["information"])
    print(f"Wrote {lesson_count} lessons, {grade_count} grades, {info_count} infos → {out}")
    print(f"overall_average: {data['overall_average']}, period_name: {data['period_name']}")
