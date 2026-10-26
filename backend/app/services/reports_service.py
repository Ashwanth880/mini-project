"""
Attendance Reporting Service.
Implements:
1. Daily attendance report
2. Student attendance report
3. Subject attendance report
4. Class attendance report
5. Monthly attendance report

Calculates for all reports:
- Present count
- Absent count
- Total classes
- Attendance percentage (from stored attendance records)

Includes date-range filtering, contextual filters, and CSV export generation.
"""

from typing import Dict, Any, List, Optional, Union
from datetime import date, datetime
import calendar
import io
import csv

from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.attendance import Attendance, AttendanceStatus
from app.models.academic import Class, Subject, ClassSubject
from app.models.student import Student
from app.models.user import User


class ReportsService:
    """Service providing aggregated attendance reports and CSV exports."""

    @staticmethod
    def _parse_date(val: Optional[Union[date, str]]) -> Optional[date]:
        """Safely parse input into a datetime.date object."""
        if val is None or val == "":
            return None
        if isinstance(val, date) and not isinstance(val, datetime):
            return val
        if isinstance(val, datetime):
            return val.date()
        if isinstance(val, str):
            clean = val.strip()
            if not clean:
                return None
            try:
                return date.fromisoformat(clean)
            except ValueError:
                # Try common formats like DD-MM-YYYY or YYYY/MM/DD
                for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%Y"):
                    try:
                        return datetime.strptime(clean, fmt).date()
                    except ValueError:
                        pass
                return None
        return None

    @staticmethod
    def _base_filtered_query(
        db: Session,
        start_date: Optional[Union[date, str]] = None,
        end_date: Optional[Union[date, str]] = None,
        class_id: Optional[int] = None,
        subject_id: Optional[int] = None,
        teacher_id: Optional[int] = None,
        department: Optional[str] = None,
    ):
        query = db.query(Attendance)
        s_date = ReportsService._parse_date(start_date)
        e_date = ReportsService._parse_date(end_date)

        if s_date:
            query = query.filter(Attendance.date >= s_date)
        if e_date:
            query = query.filter(Attendance.date <= e_date)
        if class_id:
            query = query.filter(Attendance.class_id == class_id)
        if subject_id:
            query = query.filter(Attendance.subject_id == subject_id)
        if teacher_id:
            query = query.filter(Attendance.teacher_id == teacher_id)
        if department:
            query = query.join(Class).filter(Class.department.ilike(f"%{department}%"))
        return query

    def get_daily_report(
        self,
        db: Session,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        class_id: Optional[int] = None,
        subject_id: Optional[int] = None,
        teacher_id: Optional[int] = None,
        department: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        1. Daily Attendance Report:
        Aggregates daily attendance, day-by-day session breakdowns,
        present count, absent count, total classes, and attendance percentage.
        """
        records = self._base_filtered_query(
            db, start_date=start_date, end_date=end_date,
            class_id=class_id, subject_id=subject_id,
            teacher_id=teacher_id, department=department
        ).order_by(Attendance.date.desc(), Attendance.period.asc()).all()

        total_records = len(records)
        present_count = sum(1 for r in records if r.status == AttendanceStatus.PRESENT)
        absent_count = total_records - present_count
        overall_rate = round((present_count / total_records * 100.0), 2) if total_records > 0 else 0.0

        # Unique dates
        dates_sorted = sorted(list(set(r.date for r in records)), reverse=True)
        distinct_sessions_total = len(set((r.date, r.period, r.class_id, r.subject_id) for r in records))

        daily_rows = []
        for d in dates_sorted:
            day_recs = [r for r in records if r.date == d]
            d_total = len(day_recs)
            d_pres = sum(1 for r in day_recs if r.status == AttendanceStatus.PRESENT)
            d_abs = d_total - d_pres
            d_rate = round((d_pres / d_total * 100.0), 2) if d_total > 0 else 0.0

            # Distinct sessions for this date
            day_session_keys = sorted(list(set((r.period, r.class_id, r.subject_id) for r in day_recs)))
            total_classes_on_day = len(day_session_keys)

            sessions_breakdown = []
            for p, cid, sid in day_session_keys:
                sess_recs = [r for r in day_recs if r.period == p and r.class_id == cid and r.subject_id == sid]
                s_total = len(sess_recs)
                s_pres = sum(1 for r in sess_recs if r.status == AttendanceStatus.PRESENT)
                s_abs = s_total - s_pres
                s_rate = round((s_pres / s_total * 100.0), 2) if s_total > 0 else 0.0
                first_r = sess_recs[0]

                sessions_breakdown.append({
                    "date": str(d),
                    "period": p,
                    "class_id": cid,
                    "class_name": first_r.class_group.name if first_r.class_group else f"Class {cid}",
                    "subject_id": sid,
                    "subject_code": first_r.subject.code if first_r.subject else "",
                    "subject_name": first_r.subject.name if first_r.subject else f"Subject {sid}",
                    "teacher_name": first_r.teacher.full_name if first_r.teacher else "Unassigned",
                    "total_students": s_total,
                    "present_count": s_pres,
                    "absent_count": s_abs,
                    "attendance_percentage": s_rate,
                })

            daily_rows.append({
                "date": str(d),
                "total_classes": total_classes_on_day,
                "present_count": d_pres,
                "absent_count": d_abs,
                "total_records": d_total,
                "attendance_percentage": d_rate,
                "sessions": sessions_breakdown,
            })

        return {
            "report_type": "daily",
            "report_title": "Daily Attendance Report",
            "filter": {
                "start_date": str(start_date) if start_date else None,
                "end_date": str(end_date) if end_date else None,
                "class_id": class_id,
                "subject_id": subject_id,
                "teacher_id": teacher_id,
                "department": department,
            },
            "summary": {
                "total_classes": distinct_sessions_total,
                "present_count": present_count,
                "absent_count": absent_count,
                "total_records": total_records,
                "attendance_percentage": overall_rate,
                "unique_dates_count": len(dates_sorted),
            },
            "rows": daily_rows,
        }

    def get_student_report(
        self,
        db: Session,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        class_id: Optional[int] = None,
        subject_id: Optional[int] = None,
        student_id: Optional[int] = None,
        student: Optional[str] = None,
        teacher_id: Optional[int] = None,
        department: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        2. Student Attendance Report:
        Calculates student-wise attendance: present count, absent count,
        total classes, and attendance percentage.
        Supports single student drill-down or full cohort view.
        """
        # Base query for attendance
        att_query = self._base_filtered_query(
            db, start_date=start_date, end_date=end_date,
            class_id=class_id, subject_id=subject_id,
            teacher_id=teacher_id, department=department
        )

        # Resolve student query
        students_query = db.query(Student)
        if class_id:
            students_query = students_query.filter(Student.class_id == class_id)
        if department:
            students_query = students_query.filter(Student.department.ilike(f"%{department}%"))

        if student:
            clean_s = student.strip()
            if clean_s.isdigit():
                students_query = students_query.filter(Student.id == int(clean_s))
                att_query = att_query.filter(Attendance.student_id == int(clean_s))
            else:
                students_query = students_query.filter(
                    or_(
                        Student.roll_number.ilike(f"%{clean_s}%"),
                        Student.full_name.ilike(f"%{clean_s}%"),
                        Student.register_number.ilike(f"%{clean_s}%"),
                    )
                )
                matching_ids = [s.id for s in students_query.all()]
                att_query = att_query.filter(Attendance.student_id.in_(matching_ids))
        elif student_id:
            students_query = students_query.filter(Student.id == student_id)
            att_query = att_query.filter(Attendance.student_id == student_id)

        target_students = students_query.order_by(Student.roll_number.asc()).all()
        records = att_query.all()

        total_records = len(records)
        overall_present = sum(1 for r in records if r.status == AttendanceStatus.PRESENT)
        overall_absent = total_records - overall_present
        overall_rate = round((overall_present / total_records * 100.0), 2) if total_records > 0 else 0.0

        student_rows = []
        eligible_count = 0
        shortage_count = 0

        for s in target_students:
            s_recs = [r for r in records if r.student_id == s.id]
            s_total = len(s_recs)
            s_pres = sum(1 for r in s_recs if r.status == AttendanceStatus.PRESENT)
            s_abs = s_total - s_pres
            s_rate = round((s_pres / s_total * 100.0), 2) if s_total > 0 else 0.0
            is_eligible = s_rate >= 75.0
            status_label = "Eligible" if is_eligible else ("Shortage" if s_total > 0 else "No Sessions")

            if s_total > 0:
                if is_eligible:
                    eligible_count += 1
                else:
                    shortage_count += 1

            # Individual session log if filtering a specific student
            detailed_sessions = []
            if len(target_students) <= 3:
                for r in sorted(s_recs, key=lambda x: (x.date, x.period), reverse=True):
                    detailed_sessions.append({
                        "date": str(r.date),
                        "period": r.period,
                        "subject_code": r.subject.code if r.subject else "",
                        "subject_name": r.subject.name if r.subject else "",
                        "teacher_name": r.teacher.full_name if r.teacher else "",
                        "status": r.status.value if hasattr(r.status, "value") else str(r.status),
                    })

            student_rows.append({
                "student_id": s.id,
                "roll_number": s.roll_number,
                "register_number": s.register_number,
                "full_name": s.full_name,
                "class_id": s.class_id,
                "class_name": s.class_group.name if s.class_group else "Unassigned",
                "department": s.department,
                "total_classes": s_total,
                "present_count": s_pres,
                "absent_count": s_abs,
                "total_records": s_total,
                "attendance_percentage": s_rate,
                "status_label": status_label,
                "is_shortage": not is_eligible and s_total > 0,
                "detailed_sessions": detailed_sessions,
            })

        distinct_classes_count = len(set((r.date, r.period, r.class_id, r.subject_id) for r in records))

        return {
            "report_type": "student",
            "report_title": "Student Attendance Report",
            "filter": {
                "start_date": str(start_date) if start_date else None,
                "end_date": str(end_date) if end_date else None,
                "class_id": class_id,
                "subject_id": subject_id,
                "student_id": student_id,
                "student": student,
                "teacher_id": teacher_id,
                "department": department,
            },
            "summary": {
                "total_students": len(target_students),
                "total_classes": distinct_classes_count,
                "present_count": overall_present,
                "absent_count": overall_absent,
                "total_records": total_records,
                "attendance_percentage": overall_rate,
                "eligible_count": eligible_count,
                "shortage_count": shortage_count,
            },
            "rows": student_rows,
        }

    def get_subject_report(
        self,
        db: Session,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        class_id: Optional[int] = None,
        subject_id: Optional[int] = None,
        teacher_id: Optional[int] = None,
        department: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        3. Subject Attendance Report:
        Calculates curriculum subject-wise attendance: present count, absent count,
        total classes (sessions conducted), and attendance percentage.
        """
        records = self._base_filtered_query(
            db, start_date=start_date, end_date=end_date,
            class_id=class_id, subject_id=subject_id,
            teacher_id=teacher_id, department=department
        ).all()

        total_records = len(records)
        present_count = sum(1 for r in records if r.status == AttendanceStatus.PRESENT)
        absent_count = total_records - present_count
        overall_rate = round((present_count / total_records * 100.0), 2) if total_records > 0 else 0.0

        subjects_query = db.query(Subject)
        if subject_id:
            subjects_query = subjects_query.filter(Subject.id == subject_id)
        if department:
            subjects_query = subjects_query.filter(Subject.department.ilike(f"%{department}%"))
        all_subjects = subjects_query.order_by(Subject.code.asc()).all()

        subject_rows = []
        total_sessions_all_subjects = 0

        for s in all_subjects:
            sub_recs = [r for r in records if r.subject_id == s.id]
            s_total = len(sub_recs)
            s_pres = sum(1 for r in sub_recs if r.status == AttendanceStatus.PRESENT)
            s_abs = s_total - s_pres
            s_rate = round((s_pres / s_total * 100.0), 2) if s_total > 0 else 0.0
            s_sessions = len(set((r.date, r.period, r.class_id) for r in sub_recs))
            total_sessions_all_subjects += s_sessions

            assigned_teachers = list(set(cs.teacher.full_name for cs in s.class_subjects if cs.teacher))
            classes_covered = list(set(cs.class_group.name for cs in s.class_subjects if cs.class_group))

            subject_rows.append({
                "subject_id": s.id,
                "subject_code": s.code,
                "subject_name": s.name,
                "department": s.department,
                "assigned_teachers": assigned_teachers,
                "classes_covered": classes_covered,
                "total_classes": s_sessions,
                "present_count": s_pres,
                "absent_count": s_abs,
                "total_records": s_total,
                "attendance_percentage": s_rate,
            })

        return {
            "report_type": "subject",
            "report_title": "Subject Attendance Report",
            "filter": {
                "start_date": str(start_date) if start_date else None,
                "end_date": str(end_date) if end_date else None,
                "class_id": class_id,
                "subject_id": subject_id,
                "teacher_id": teacher_id,
                "department": department,
            },
            "summary": {
                "total_subjects": len(all_subjects),
                "total_classes": total_sessions_all_subjects,
                "present_count": present_count,
                "absent_count": absent_count,
                "total_records": total_records,
                "attendance_percentage": overall_rate,
            },
            "rows": subject_rows,
        }

    def get_class_report(
        self,
        db: Session,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        class_id: Optional[int] = None,
        department: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        4. Class Attendance Report:
        Calculates cohort class-wise attendance: present count, absent count,
        total classes (sessions conducted), enrolled strength, and attendance percentage.
        """
        records = self._base_filtered_query(
            db, start_date=start_date, end_date=end_date,
            class_id=class_id, department=department
        ).all()

        total_records = len(records)
        present_count = sum(1 for r in records if r.status == AttendanceStatus.PRESENT)
        absent_count = total_records - present_count
        overall_rate = round((present_count / total_records * 100.0), 2) if total_records > 0 else 0.0

        classes_query = db.query(Class)
        if class_id:
            classes_query = classes_query.filter(Class.id == class_id)
        if department:
            classes_query = classes_query.filter(Class.department.ilike(f"%{department}%"))
        all_classes = classes_query.order_by(Class.year.asc(), Class.section.asc()).all()

        class_rows = []
        total_sessions_all_classes = 0

        for c in all_classes:
            c_recs = [r for r in records if r.class_id == c.id]
            c_total = len(c_recs)
            c_pres = sum(1 for r in c_recs if r.status == AttendanceStatus.PRESENT)
            c_abs = c_total - c_pres
            c_rate = round((c_pres / c_total * 100.0), 2) if c_total > 0 else 0.0
            c_sessions = len(set((r.date, r.period, r.subject_id) for r in c_recs))
            total_sessions_all_classes += c_sessions

            class_rows.append({
                "class_id": c.id,
                "class_name": c.name,
                "department": c.department,
                "year": c.year,
                "section": c.section,
                "class_teacher_name": c.class_teacher.full_name if c.class_teacher else "Unassigned",
                "enrolled_students": len(c.students),
                "total_classes": c_sessions,
                "present_count": c_pres,
                "absent_count": c_abs,
                "total_records": c_total,
                "attendance_percentage": c_rate,
                "status_label": "Good Standing" if c_rate >= 75.0 else ("Attention Needed" if c_total > 0 else "No Sessions"),
            })

        return {
            "report_type": "class",
            "report_title": "Class Attendance Report",
            "filter": {
                "start_date": str(start_date) if start_date else None,
                "end_date": str(end_date) if end_date else None,
                "class_id": class_id,
                "department": department,
            },
            "summary": {
                "total_classes_count": len(all_classes),
                "total_classes": total_sessions_all_classes,
                "present_count": present_count,
                "absent_count": absent_count,
                "total_records": total_records,
                "attendance_percentage": overall_rate,
            },
            "rows": class_rows,
        }

    def get_monthly_report(
        self,
        db: Session,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        year: Optional[int] = None,
        month: Optional[int] = None,
        class_id: Optional[int] = None,
        subject_id: Optional[int] = None,
        department: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        5. Monthly Attendance Report:
        Calculates month-by-month attendance: working days, total classes conducted,
        present count, absent count, total records, and monthly attendance percentage.
        """
        # If year/month provided without start/end date, constrain to that month
        if year and month and not start_date and not end_date:
            last_day = calendar.monthrange(year, month)[1]
            start_date = date(year, month, 1)
            end_date = date(year, month, last_day)

        records = self._base_filtered_query(
            db, start_date=start_date, end_date=end_date,
            class_id=class_id, subject_id=subject_id, department=department
        ).order_by(Attendance.date.desc()).all()

        total_records = len(records)
        present_count = sum(1 for r in records if r.status == AttendanceStatus.PRESENT)
        absent_count = total_records - present_count
        overall_rate = round((present_count / total_records * 100.0), 2) if total_records > 0 else 0.0

        # Group by (year, month)
        month_keys = sorted(list(set((r.date.year, r.date.month) for r in records)), reverse=True)
        monthly_rows = []
        total_sessions_all = len(set((r.date, r.period, r.class_id, r.subject_id) for r in records))
        total_working_days_all = len(set(r.date for r in records))

        for y, m in month_keys:
            m_recs = [r for r in records if r.date.year == y and r.date.month == m]
            m_total = len(m_recs)
            m_pres = sum(1 for r in m_recs if r.status == AttendanceStatus.PRESENT)
            m_abs = m_total - m_pres
            m_rate = round((m_pres / m_total * 100.0), 2) if m_total > 0 else 0.0

            working_days = len(set(r.date for r in m_recs))
            m_classes = len(set((r.date, r.period, r.class_id, r.subject_id) for r in m_recs))
            month_name = f"{calendar.month_name[m]} {y}"
            month_key = f"{y}-{m:02d}"

            monthly_rows.append({
                "month_key": month_key,
                "month_name": month_name,
                "year": y,
                "month": m,
                "working_days_count": working_days,
                "total_classes": m_classes,
                "present_count": m_pres,
                "absent_count": m_abs,
                "total_records": m_total,
                "attendance_percentage": m_rate,
            })

        return {
            "report_type": "monthly",
            "report_title": "Monthly Attendance Report",
            "filter": {
                "start_date": str(start_date) if start_date else None,
                "end_date": str(end_date) if end_date else None,
                "year": year,
                "month": month,
                "class_id": class_id,
                "subject_id": subject_id,
                "department": department,
            },
            "summary": {
                "total_months": len(month_keys),
                "working_days_count": total_working_days_all,
                "total_classes": total_sessions_all,
                "present_count": present_count,
                "absent_count": absent_count,
                "total_records": total_records,
                "attendance_percentage": overall_rate,
            },
            "rows": monthly_rows,
        }

    def generate_csv_string(self, report_data: Dict[str, Any]) -> str:
        """
        Converts any of the 5 report data dictionaries into a clean CSV string
        with institutional metadata and accurate columns.
        """
        output = io.StringIO()
        writer = csv.writer(output)

        report_type = report_data.get("report_type", "attendance")
        title = report_data.get("report_title", "Attendance Report")
        summary = report_data.get("summary", {})
        filt = report_data.get("filter", {})
        rows = report_data.get("rows", [])

        # Institutional Header Comments
        writer.writerow([f"# ONE-CLICK ATTENDANCE SYSTEM - {title.upper()}"])
        writer.writerow([f"# Generated On: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"])
        date_str = f"{filt.get('start_date') or 'Earliest'} to {filt.get('end_date') or 'Latest'}"
        writer.writerow([f"# Date Range: {date_str}"])
        writer.writerow([
            f"# Summary: Present Count={summary.get('present_count', 0)}, "
            f"Absent Count={summary.get('absent_count', 0)}, "
            f"Total Classes={summary.get('total_classes', 0)}, "
            f"Attendance Percentage={summary.get('attendance_percentage', 0.0):.2f}%"
        ])
        writer.writerow([])

        if report_type == "daily":
            writer.writerow([
                "Date", "Total Classes Conducted", "Present Count", "Absent Count",
                "Total Student Records", "Attendance Percentage (%)"
            ])
            for r in rows:
                writer.writerow([
                    r.get("date"),
                    r.get("total_classes"),
                    r.get("present_count"),
                    r.get("absent_count"),
                    r.get("total_records"),
                    f"{r.get('attendance_percentage', 0.0):.2f}%",
                ])

        elif report_type == "student":
            writer.writerow([
                "Roll Number", "Student Name", "Register Number", "Class Section",
                "Total Classes", "Present Count", "Absent Count", "Attendance Percentage (%)", "Eligibility Status"
            ])
            for r in rows:
                writer.writerow([
                    r.get("roll_number"),
                    r.get("full_name"),
                    r.get("register_number"),
                    r.get("class_name"),
                    r.get("total_classes"),
                    r.get("present_count"),
                    r.get("absent_count"),
                    f"{r.get('attendance_percentage', 0.0):.2f}%",
                    r.get("status_label"),
                ])

        elif report_type == "subject":
            writer.writerow([
                "Subject Code", "Subject Name", "Department", "Faculty In-Charge",
                "Classes Covered", "Total Classes Conducted", "Present Count", "Absent Count",
                "Total Student Records", "Attendance Percentage (%)"
            ])
            for r in rows:
                teachers = ", ".join(r.get("assigned_teachers", [])) or "Unassigned"
                classes = ", ".join(r.get("classes_covered", [])) or "None"
                writer.writerow([
                    r.get("subject_code"),
                    r.get("subject_name"),
                    r.get("department"),
                    teachers,
                    classes,
                    r.get("total_classes"),
                    r.get("present_count"),
                    r.get("absent_count"),
                    r.get("total_records"),
                    f"{r.get('attendance_percentage', 0.0):.2f}%",
                ])

        elif report_type == "class":
            writer.writerow([
                "Class Name", "Department", "Year", "Section", "Class Teacher",
                "Enrolled Students", "Total Classes Conducted", "Present Count", "Absent Count",
                "Total Student Records", "Attendance Percentage (%)", "Standing Status"
            ])
            for r in rows:
                writer.writerow([
                    r.get("class_name"),
                    r.get("department"),
                    r.get("year"),
                    r.get("section"),
                    r.get("class_teacher_name"),
                    r.get("enrolled_students"),
                    r.get("total_classes"),
                    r.get("present_count"),
                    r.get("absent_count"),
                    r.get("total_records"),
                    f"{r.get('attendance_percentage', 0.0):.2f}%",
                    r.get("status_label"),
                ])

        elif report_type == "monthly":
            writer.writerow([
                "Month", "Working Days with Attendance", "Total Classes Conducted",
                "Present Count", "Absent Count", "Total Student Records", "Attendance Percentage (%)"
            ])
            for r in rows:
                writer.writerow([
                    r.get("month_name"),
                    r.get("working_days_count"),
                    r.get("total_classes"),
                    r.get("present_count"),
                    r.get("absent_count"),
                    r.get("total_records"),
                    f"{r.get('attendance_percentage', 0.0):.2f}%",
                ])

        return output.getvalue()

    def get_report(self, report_type: str, db: Session, **kwargs) -> Dict[str, Any]:
        """
        Master dispatcher to retrieve any of the 5 attendance reports:
        1. daily
        2. student
        3. subject
        4. class
        5. monthly
        """
        rt = (report_type or "daily").lower().strip()
        if rt == "daily":
            return self.get_daily_report(
                db,
                start_date=kwargs.get("start_date"),
                end_date=kwargs.get("end_date"),
                class_id=kwargs.get("class_id"),
                subject_id=kwargs.get("subject_id"),
                teacher_id=kwargs.get("teacher_id"),
                department=kwargs.get("department"),
            )
        elif rt == "student":
            return self.get_student_report(
                db,
                start_date=kwargs.get("start_date"),
                end_date=kwargs.get("end_date"),
                class_id=kwargs.get("class_id"),
                subject_id=kwargs.get("subject_id"),
                student_id=kwargs.get("student_id"),
                student=kwargs.get("student"),
                teacher_id=kwargs.get("teacher_id"),
                department=kwargs.get("department"),
            )
        elif rt == "subject":
            return self.get_subject_report(
                db,
                start_date=kwargs.get("start_date"),
                end_date=kwargs.get("end_date"),
                class_id=kwargs.get("class_id"),
                subject_id=kwargs.get("subject_id"),
                teacher_id=kwargs.get("teacher_id"),
                department=kwargs.get("department"),
            )
        elif rt == "class":
            return self.get_class_report(
                db,
                start_date=kwargs.get("start_date"),
                end_date=kwargs.get("end_date"),
                class_id=kwargs.get("class_id"),
                department=kwargs.get("department"),
            )
        elif rt == "monthly":
            return self.get_monthly_report(
                db,
                start_date=kwargs.get("start_date"),
                end_date=kwargs.get("end_date"),
                year=kwargs.get("year"),
                month=kwargs.get("month"),
                class_id=kwargs.get("class_id"),
                subject_id=kwargs.get("subject_id"),
                department=kwargs.get("department"),
            )
        else:
            raise ValueError(f"Unknown report type '{report_type}'. Expected one of: daily, student, subject, class, monthly.")


reports_service = ReportsService()
