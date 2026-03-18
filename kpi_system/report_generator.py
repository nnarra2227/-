import os
import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.platypus import KeepTogether
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import arabic_reshaper
from bidi.algorithm import get_display

# Register Arabic font
FONT_PATH = os.path.join(os.path.dirname(__file__), 'static', 'fonts', 'NotoSansArabic.ttf')
FONT_BOLD_PATH = os.path.join(os.path.dirname(__file__), 'static', 'fonts', 'NotoSansArabic-Bold.ttf')

def setup_fonts():
    try:
        if os.path.exists(FONT_PATH):
            pdfmetrics.registerFont(TTFont('Arabic', FONT_PATH))
        if os.path.exists(FONT_BOLD_PATH):
            pdfmetrics.registerFont(TTFont('ArabicBold', FONT_BOLD_PATH))
        return True
    except:
        return False

def ar(text):
    """Reshape and apply bidi to Arabic text"""
    if not text:
        return ''
    try:
        reshaped = arabic_reshaper.reshape(str(text))
        return get_display(reshaped)
    except:
        return str(text)

def generate_pdf_report(report_type, year, dept_id=None, quarter=None, month=None):
    from app import app, db
    from models import KPI, KPIResult, Department

    fonts_ok = setup_fonts()
    font_name = 'Arabic' if fonts_ok and os.path.exists(FONT_PATH) else 'Helvetica'
    font_bold = 'ArabicBold' if fonts_ok and os.path.exists(FONT_BOLD_PATH) else 'Helvetica-Bold'

    output_dir = os.path.join(os.path.dirname(__file__), 'instance')
    os.makedirs(output_dir, exist_ok=True)
    pdf_path = os.path.join(output_dir, f'report_{report_type}_{year}_{datetime.now().strftime("%Y%m%d%H%M%S")}.pdf')

    doc = SimpleDocTemplate(pdf_path, pagesize=A4,
                            rightMargin=1.5*cm, leftMargin=1.5*cm,
                            topMargin=2*cm, bottomMargin=2*cm)

    # Colors
    PRIMARY = colors.HexColor('#1e3a5f')
    SECONDARY = colors.HexColor('#2980b9')
    GREEN = colors.HexColor('#27ae60')
    RED = colors.HexColor('#e74c3c')
    LIGHT_BLUE = colors.HexColor('#ebf5fb')
    LIGHT_GRAY = colors.HexColor('#f8f9fa')

    styles = {
        'title': ParagraphStyle('title', fontName=font_bold, fontSize=18,
                                 alignment=TA_CENTER, textColor=PRIMARY, spaceAfter=6),
        'subtitle': ParagraphStyle('subtitle', fontName=font_name, fontSize=12,
                                    alignment=TA_CENTER, textColor=SECONDARY, spaceAfter=12),
        'heading': ParagraphStyle('heading', fontName=font_bold, fontSize=13,
                                   alignment=TA_RIGHT, textColor=PRIMARY, spaceAfter=6, spaceBefore=12),
        'normal': ParagraphStyle('normal', fontName=font_name, fontSize=10,
                                  alignment=TA_RIGHT, spaceAfter=4),
        'small': ParagraphStyle('small', fontName=font_name, fontSize=9,
                                 alignment=TA_RIGHT, textColor=colors.gray),
    }

    story = []
    months_ar = ['يناير','فبراير','مارس','أبريل','مايو','يونيو',
                 'يوليو','أغسطس','سبتمبر','أكتوبر','نوفمبر','ديسمبر']

    with app.app_context():
        # Header
        story.append(Paragraph(ar('المركز الصحي الأولي'), styles['title']))
        story.append(Paragraph(ar('نظام إدارة مؤشرات الأداء'), styles['subtitle']))
        story.append(HRFlowable(width="100%", thickness=2, color=PRIMARY))
        story.append(Spacer(1, 0.3*cm))

        if report_type == 'monthly' and month:
            title_text = f"التقرير الشهري - {months_ar[int(month)-1]} {year}"
            results_query = KPIResult.query.filter_by(year=year, month=int(month))
        elif report_type == 'quarterly' and quarter:
            title_text = f"التقرير الربع سنوي - الربع {quarter} - {year}"
            results_query = KPIResult.query.filter_by(year=year, quarter=int(quarter))
        elif report_type == 'department' and dept_id:
            dept = Department.query.get(int(dept_id))
            dept_name = dept.name if dept else 'القسم'
            title_text = f"تقرير أداء {dept_name} - {year}"
            kpi_ids = [k.id for k in KPI.query.filter_by(department_id=int(dept_id), is_active=True).all()]
            results_query = KPIResult.query.filter(KPIResult.kpi_id.in_(kpi_ids), KPIResult.year == year)
        else:
            title_text = f"التقرير السنوي - {year}"
            results_query = KPIResult.query.filter_by(year=year)

        story.append(Paragraph(ar(title_text), styles['heading']))
        story.append(Paragraph(ar(f"تاريخ الإصدار: {datetime.now().strftime('%Y/%m/%d')}"), styles['small']))
        story.append(Spacer(1, 0.5*cm))

        results = results_query.all()

        # Summary stats
        achieved = sum(1 for r in results if r.is_achieved() is True)
        not_achieved = sum(1 for r in results if r.is_achieved() is False)
        total = len(results)
        pct = round((achieved / total) * 100, 1) if total > 0 else 0

        summary_data = [
            [ar('إجمالي النتائج'), ar('المحقق'), ar('غير المحقق'), ar('نسبة التحقيق')],
            [str(total), str(achieved), str(not_achieved), f'{pct}%']
        ]
        summary_table = Table(summary_data, colWidths=[4*cm, 4*cm, 4*cm, 4*cm])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), PRIMARY),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,-1), font_bold),
            ('FONTSIZE', (0,0), (-1,-1), 11),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [LIGHT_BLUE, colors.white]),
            ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
            ('TOPPADDING', (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 0.5*cm))

        # Main results table
        story.append(Paragraph(ar('تفاصيل المؤشرات'), styles['heading']))

        table_data = [[ar('المؤشر'), ar('القسم'), ar('النتيجة %'), ar('المستهدف %'), ar('الحالة'), ar('التحليل')]]

        for r in results:
            kpi = r.kpi
            dept_name = kpi.department.name if kpi.department else '-'
            result_val = f"{r.result_value}%" if r.result_value is not None else '-'
            target_val = f"{r.target_value or kpi.target_value}%" if (r.target_value or kpi.target_value) is not None else '-'
            status = ar('محقق ✓') if r.is_achieved() is True else (ar('غير محقق ✗') if r.is_achieved() is False else ar('-'))
            analysis_text = (r.analysis or '')[:60] + ('...' if len(r.analysis or '') > 60 else '')

            row = [
                Paragraph(ar(kpi.name[:50]), ParagraphStyle('cell', fontName=font_name, fontSize=8, alignment=TA_RIGHT)),
                Paragraph(ar(dept_name), ParagraphStyle('cell', fontName=font_name, fontSize=8, alignment=TA_CENTER)),
                Paragraph(result_val, ParagraphStyle('cell', fontName=font_name, fontSize=9, alignment=TA_CENTER)),
                Paragraph(target_val, ParagraphStyle('cell', fontName=font_name, fontSize=9, alignment=TA_CENTER)),
                Paragraph(status, ParagraphStyle('cell', fontName=font_bold, fontSize=9, alignment=TA_CENTER,
                    textColor=GREEN if r.is_achieved() is True else (RED if r.is_achieved() is False else colors.gray))),
                Paragraph(ar(analysis_text), ParagraphStyle('cell', fontName=font_name, fontSize=7, alignment=TA_RIGHT)),
            ]
            table_data.append(row)

        if len(table_data) > 1:
            col_widths = [5.5*cm, 3*cm, 2*cm, 2*cm, 2*cm, 4*cm]
            main_table = Table(table_data, colWidths=col_widths, repeatRows=1)
            main_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), PRIMARY),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('FONTNAME', (0,0), (-1,0), font_bold),
                ('FONTSIZE', (0,0), (-1,0), 10),
                ('ALIGN', (0,0), (-1,0), 'CENTER'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, LIGHT_GRAY]),
                ('GRID', (0,0), (-1,-1), 0.3, colors.lightgrey),
                ('TOPPADDING', (0,0), (-1,-1), 5),
                ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ]))
            story.append(main_table)
        else:
            story.append(Paragraph(ar('لا توجد بيانات لهذه الفترة'), styles['normal']))

        story.append(Spacer(1, 1*cm))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.lightgrey))
        story.append(Paragraph(ar(f'تم إنشاء هذا التقرير بواسطة نظام إدارة مؤشرات الأداء - {datetime.now().strftime("%Y/%m/%d %H:%M")}'),
                                styles['small']))

    doc.build(story)
    return pdf_path
