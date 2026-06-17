from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from app.models import WaterAssessment

class PDFService:
    """Service to generate professional PDF reports for water assessments."""
    
    @staticmethod
    def generate_assessment_report(assessment: WaterAssessment) -> BytesIO:
        """
        Builds a styled PDF document in memory and returns its byte buffer.
        
        Args:
            assessment (WaterAssessment): The database model record.
            
        Returns:
            BytesIO: In-memory binary file stream.
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=45,
            leftMargin=45,
            topMargin=45,
            bottomMargin=45
        )
        
        story = []
        styles = getSampleStyleSheet()
        
        # Define high-fidelity SaaS color styling
        primary_color = colors.HexColor("#0284c7")  # Deep Sky Blue
        text_dark = colors.HexColor("#0f172a")      # Slate 900
        text_muted = colors.HexColor("#64748b")     # Slate 500
        border_grey = colors.HexColor("#e2e8f0")    # Slate 200
        
        # Custom Typography Styles
        title_style = ParagraphStyle(
            name="ReportTitle",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=26,
            textColor=primary_color,
            spaceAfter=6
        )
        
        meta_style = ParagraphStyle(
            name="ReportMeta",
            parent=styles["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=9,
            leading=12,
            textColor=text_muted,
            spaceAfter=15
        )
        
        section_style = ParagraphStyle(
            name="SectionHeading",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=text_dark,
            spaceBefore=14,
            spaceAfter=6,
            keepWithNext=True
        )
        
        body_style = ParagraphStyle(
            name="BodyTextCustom",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#334155")
        )
        
        bullet_style = ParagraphStyle(
            name="BulletCustom",
            parent=body_style,
            leftIndent=15,
            firstLineIndent=-10,
            spaceAfter=4
        )

        # 1. Document Title & Metadata
        story.append(Paragraph("HydroSafe Diagnostic Safety Report", title_style))
        date_str = assessment.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC") if assessment.timestamp else "N/A"
        story.append(Paragraph(
            f"Sample ID: #{assessment.id}  |  Generated: {date_str}  |  Origin: {assessment.user_location or 'Unknown'}",
            meta_style
        ))
        
        # 2. Quality Classification Summary
        story.append(Paragraph("1. Quality Classification Summary", section_style))
        is_safe = assessment.prediction == "Potable"
        status_text = "POTABLE (Safe to drink)" if is_safe else "NOT POTABLE (Potential health risk)"
        status_color = "#059669" if is_safe else "#e11d48"
        
        story.append(Paragraph(
            f"The analyzed sample is classified as: <b><font color='{status_color}'>{status_text}</font></b>",
            body_style
        ))
        story.append(Paragraph(
            f"XGBoost Classifier prediction confidence is <b>{assessment.confidence_score * 100:.1f}%</b>. "
            f"The rule-based compliance scoring engine evaluates the sample safety index at "
            f"<b>{assessment.water_safety_score}/100</b>, placing it in the <b>{assessment.water_safety_category.upper()}</b> quality category.",
            body_style
        ))
        story.append(Spacer(1, 10))
        
        # 3. Chemical Parameters Table
        story.append(Paragraph("2. Chemical Parameter Readings & WHO Safe Ranges", section_style))
        
        def check_status(val, min_val, max_val):
            return "PASS" if min_val <= val <= max_val else "FAIL"
            
        table_data = [
            ["Chemical Parameter", "WHO Standard Range", "Measured Value", "Compliance"],
            ["pH Level", "6.5 – 8.5", f"{assessment.ph:.2f}", check_status(assessment.ph, 6.5, 8.5)],
            ["Dissolved Solids (TDS)", "< 1000 ppm", f"{assessment.solids:.0f} ppm", check_status(assessment.solids, 0, 1000)],
            ["Chloramines", "< 4.0 ppm", f"{assessment.chloramines:.2f} ppm", check_status(assessment.chloramines, 0, 4.0)],
            ["Sulfate", "< 250 mg/L", f"{assessment.sulfate:.0f} mg/L", check_status(assessment.sulfate, 0, 250)],
            ["Turbidity", "< 5.0 NTU", f"{assessment.turbidity:.2f} NTU", check_status(assessment.turbidity, 0, 5.0)]
        ]
        
        t = Table(table_data, colWidths=[150, 120, 110, 100])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f1f5f9")),
            ('TEXTCOLOR', (0,0), (-1,0), text_dark),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 9),
            ('BOTTOMPADDING', (0,0), (-1,0), 5),
            ('TOPPADDING', (0,0), (-1,0), 5),
            ('GRID', (0,0), (-1,-1), 0.5, border_grey),
            ('ALIGN', (1,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TEXTCOLOR', (3,1), (3,-1), colors.HexColor("#059669")), # Green for pass
            ('FONTSIZE', (0,1), (-1,-1), 9),
            ('BOTTOMPADDING', (0,1), (-1,-1), 4),
            ('TOPPADDING', (0,1), (-1,-1), 4),
        ]))
        
        # Style FAIL lines with bold red compliance text
        for idx in range(1, 6):
            if table_data[idx][3] == "FAIL":
                t.setStyle(TableStyle([
                    ('TEXTCOLOR', (3, idx), (3, idx), colors.HexColor("#e11d48")),
                    ('FONTNAME', (3, idx), (3, idx), 'Helvetica-Bold')
                ]))
                
        story.append(t)
        story.append(Spacer(1, 10))
        
        # 4. Treatment Guidelines
        story.append(Paragraph("3. Water Treatment & Mitigation Guidelines", section_style))
        recs = assessment.recommendations
        if recs:
            for idx, rec in enumerate(recs):
                story.append(Paragraph(f"<b>{idx + 1}.</b> {rec}", bullet_style))
        else:
            story.append(Paragraph("All chemical metrics meet standard guidelines. Maintain standard filtration systems.", body_style))
            
        story.append(Spacer(1, 12))
        
        # 5. Rationale & Quality Assurance
        story.append(Paragraph("4. Quality Assurance and Validation", section_style))
        story.append(Paragraph(
            "This report is compiled automatically based on active XGBoost model boundary parameters and WHO regulations. "
            "Verification logs are saved in the municipal registry database. Direct chemical titrations should be conducted "
            "periodically to audit sensor metrics and validate model thresholds.",
            body_style
        ))
        story.append(Spacer(1, 25))
        
        # Footer text
        story.append(Paragraph(
            "<b>HydroSafe Labs Inc.</b>  |  Environmental Science & Water Quality Telemetry Systems",
            ParagraphStyle(
                name="FooterText",
                parent=styles["Normal"],
                fontName="Helvetica-Bold",
                fontSize=8,
                textColor=text_muted,
                alignment=1
            )
        ))
        
        doc.build(story)
        buffer.seek(0)
        return buffer
