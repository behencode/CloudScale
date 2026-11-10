from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    Flowable,
    KeepTogether,
    LongTable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "pdf" / "cloudscale-project-report.pdf"
OUT.parent.mkdir(parents=True, exist_ok=True)

NAVY = colors.HexColor("#12304A")
BLUE = colors.HexColor("#216E9B")
TEAL = colors.HexColor("#168C88")
PALE = colors.HexColor("#EAF2F7")
LIGHT = colors.HexColor("#F5F8FA")
INK = colors.HexColor("#243746")
MUTED = colors.HexColor("#5B6B78")

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(
    name="CoverTitle", parent=styles["Title"], fontName="Helvetica-Bold",
    fontSize=25, leading=30, textColor=NAVY, alignment=TA_LEFT, spaceAfter=9,
))
styles.add(ParagraphStyle(
    name="Subtitle", parent=styles["Normal"], fontName="Helvetica",
    fontSize=12, leading=17, textColor=MUTED, spaceAfter=12,
))
styles.add(ParagraphStyle(
    name="Section", parent=styles["Heading1"], fontName="Helvetica-Bold",
    fontSize=16, leading=20, textColor=NAVY, spaceBefore=8, spaceAfter=8,
))
styles.add(ParagraphStyle(
    name="Subsection", parent=styles["Heading2"], fontName="Helvetica-Bold",
    fontSize=10, leading=13, textColor=BLUE, spaceBefore=7, spaceAfter=4,
))
styles.add(ParagraphStyle(
    name="BodySmall", parent=styles["BodyText"], fontName="Helvetica",
    fontSize=8.4, leading=12, textColor=INK, spaceAfter=5,
))
styles.add(ParagraphStyle(
    name="Tiny", parent=styles["BodyText"], fontName="Helvetica",
    fontSize=7.2, leading=9.5, textColor=MUTED,
))
styles.add(ParagraphStyle(
    name="TableHead", parent=styles["BodyText"], fontName="Helvetica-Bold",
    fontSize=7.6, leading=9.5, textColor=colors.white,
))
styles.add(ParagraphStyle(
    name="TableBody", parent=styles["BodyText"], fontName="Helvetica",
    fontSize=7.4, leading=9.6, textColor=INK,
))
styles.add(ParagraphStyle(
    name="Callout", parent=styles["BodyText"], fontName="Helvetica-Bold",
    fontSize=9, leading=13, textColor=NAVY,
))
def P(text, style="BodySmall"):
    return Paragraph(text, styles[style])


class ArchitectureDiagram(Flowable):
    def __init__(self, width=7.05 * inch, height=2.16 * inch):
        super().__init__()
        self.width = width
        self.height = height

    def draw(self):
        c = self.canv
        w, h = self.width, self.height
        nodes = {
            "user": (6, h - 35, 75, 25, "Students", PALE),
            "cf": (102, h - 35, 105, 25, "CloudFront", PALE),
            "s3web": (233, h - 35, 105, 25, "Private S3\nfrontend", PALE),
            "alb": (102, h - 82, 105, 25, "Public ALB", PALE),
            "ec2": (233, h - 82, 150, 25, "Private EC2 ASG (2)", PALE),
            "data": (414, h - 82, 120, 25, "DynamoDB + S3", PALE),
            "auth": (6, h - 132, 110, 25, "Cognito", LIGHT),
            "ai": (137, h - 132, 110, 25, "Bedrock", LIGHT),
            "queue": (268, h - 132, 100, 25, "SQS", LIGHT),
            "lambda": (389, h - 132, 100, 25, "Lambda", LIGHT),
            "sns": (510, h - 132, 72, 25, "SNS", LIGHT),
        }
        scale_x = w / (590)
        for key, (x, y, nw, nh, label, fill) in nodes.items():
            x, nw = x * scale_x, nw * scale_x
            c.setFillColor(fill)
            c.setStrokeColor(colors.HexColor("#B8CBD7"))
            c.roundRect(x, y, nw, nh, 5, fill=1, stroke=1)
            c.setFillColor(NAVY)
            lines = label.split("\n")
            c.setFont("Helvetica-Bold", 7.1)
            if len(lines) == 1:
                c.drawCentredString(x + nw / 2, y + 9, label)
            else:
                c.drawCentredString(x + nw / 2, y + 14, lines[0])
                c.drawCentredString(x + nw / 2, y + 5, lines[1])

        def arrow(a, b, color=BLUE, dashed=False):
            ax, ay, aw, ah, *_ = nodes[a]
            bx, by, bw, bh, *_ = nodes[b]
            ax, aw, bx, bw = ax * scale_x, aw * scale_x, bx * scale_x, bw * scale_x
            x1, y1 = ax + aw, ay + ah / 2
            x2, y2 = bx, by + bh / 2
            if b in ("alb", "auth", "ai", "queue"):
                x1, y1 = ax + aw / 2, ay
                x2, y2 = bx + bw / 2, by + bh
            c.setStrokeColor(color)
            c.setFillColor(color)
            if dashed:
                c.setDash(3, 2)
            else:
                c.setDash()
            c.line(x1, y1, x2, y2)
            c.setDash()
            c.line(x2, y2, x2 - 4, y2 + 2)
            c.line(x2, y2, x2 - 4, y2 - 2)

        arrow("user", "cf")
        arrow("cf", "s3web")
        arrow("cf", "alb")
        arrow("alb", "ec2")
        arrow("ec2", "data")
        arrow("ec2", "auth", TEAL, True)
        arrow("ec2", "ai", TEAL, True)
        arrow("ec2", "queue", TEAL, True)
        arrow("queue", "lambda", TEAL)
        arrow("lambda", "sns", TEAL)
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 6.5)
        c.drawString(5, 5, "Dashed arrows are AWS service calls; EC2 instances run in private subnets across two AZs.")


def table(data, widths, header=True, row_bgs=None):
    t = LongTable(data, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    commands = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D5E0E7")),
    ]
    if header:
        commands.extend([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ])
    for idx in range(1 if header else 0, len(data)):
        commands.append(("BACKGROUND", (0, idx), (-1, idx), LIGHT if idx % 2 else colors.white))
    t.setStyle(TableStyle(commands))
    return t


def footer(canvas, doc):
    canvas.saveState()
    width, height = letter
    canvas.setStrokeColor(colors.HexColor("#D5E0E7"))
    canvas.line(doc.leftMargin, 0.58 * inch, width - doc.rightMargin, 0.58 * inch)
    canvas.setFont("Helvetica", 7.2)
    canvas.setFillColor(MUTED)
    canvas.drawString(doc.leftMargin, 0.38 * inch, "CS-4075 CloudScale | CampusConnect Project Report")
    canvas.drawRightString(width - doc.rightMargin, 0.38 * inch, f"Page {doc.page}")
    canvas.restoreState()


story = []
story += [
    Spacer(1, 0.20 * inch),
    P("CS-4075 | CLOUD COMPUTING", "Subsection"),
    P("CampusConnect", "CoverTitle"),
    P("Cloud project implementation and deployment report", "Subtitle"),
    P("Prepared 10 November 2026 | Deployed in AWS us-east-1", "BodySmall"),
    Spacer(1, 0.05 * inch),
]
callout = Table([[P("LIVE DEMO  <link href='https://d39xic7jvhqh80.cloudfront.net' color='#216E9B'>https://d39xic7jvhqh80.cloudfront.net</link>", "Callout")]], colWidths=[7.05 * inch])
callout.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, -1), PALE),
    ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#B8CBD7")),
    ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
]))
story += [callout, Spacer(1, 0.12 * inch), P("Executive summary", "Section")]
story += [P(
    "CampusConnect is a campus resource board for lost-and-found items, textbook exchange, housing, events, and community requests. "
    "The deployed system serves a React frontend through CloudFront and routes API requests to a FastAPI backend on a private two-instance EC2 Auto Scaling group behind an Application Load Balancer. "
    "The application health endpoint returned HTTP 200 with no configuration warnings during final verification."
)]
story += [P(
    "The live setup demonstrates multi-service AWS infrastructure and a working web/API path. Several user-facing cloud operations were not exercised end-to-end before submission. "
    "This report separates deployed configuration from behavior that remains unverified; it does not claim a trained SageMaker model, a scaling demonstration, or billing-history evidence."
)]
story += [P(
    "For the student video walkthrough, a local-only seed script creates eight fictional listings and two notifications in a separate ignored SQLite file. "
    "Those records are not written to AWS. The recording outline and startup steps are in docs/video-demo-guide.md."
)]
story += [P("System architecture", "Section"), ArchitectureDiagram(), Spacer(1, 4)]
story += [P(
    "CloudFront serves the static frontend from a private S3 origin and forwards API traffic to the ALB. The ALB reaches private EC2 instances in two Availability Zones. "
    "The backend is configured to use Cognito, DynamoDB, S3, Bedrock descriptions, local category suggestions, and AWS notifications. Image work is wired through SQS to Lambda, with an SQS dead-letter queue."
)]

story += [P("AWS service choices and deployment status", "Section")]
service_rows = [
    [P("Layer", "TableHead"), P("Choice and application purpose", "TableHead"), P("Observed status", "TableHead")],
    [P("Networking", "TableBody"), P("Custom two-AZ VPC separates public ALB ingress from private EC2 compute. NAT supports outbound package/service access; CloudFront prefix-list restriction narrows origin ingress.", "TableBody"), P("Deployed. Two public and two private subnets, IGW, NAT, security groups, and S3/DynamoDB gateway endpoints.", "TableBody")],
    [P("Compute", "TableBody"), P("EC2 Auto Scaling group supplies a minimum of two API instances; ALB health checks route requests and a CPU policy supports scale-out.", "TableBody"), P("Before the user's manual stop, desired 2 and both targets were healthy. User reports no replacement after stopping one instance; current capacity needs recheck. Refresh was cancelled at 50% after stale health-data status.", "TableBody")],
    [P("Storage/CDN", "TableBody"), P("S3 stores frontend objects and uploaded media; versioning/lifecycle support recovery and retention. CloudFront provides HTTPS delivery and caching.", "TableBody"), P("Private S3 origin and CloudFront deployed. Cognito-enabled frontend uploaded; invalidation completed. Live user upload not tested.", "TableBody")],
    [P("Data", "TableBody"), P("DynamoDB was selected for keyed listing/profile access and on-demand capacity; a gateway endpoint keeps table traffic on AWS networking.", "TableBody"), P("Table and indexes deployed. Live CRUD/persistence not tested.", "TableBody")],
    [P("Serverless", "TableBody"), P("Lambda creates a processed image asynchronously, keeping image work out of the request path.", "TableBody"), P("Function Active and SQS event mapping deployed. Actual queue invocation not verified.", "TableBody")],
    [P("Messaging", "TableBody"), P("SQS buffers image jobs and DLQ retains repeatedly failed work. SNS supports listing/worker event notifications.", "TableBody"), P("Queue, DLQ, and SNS topic deployed. Email subscription confirmation and delivery not verified.", "TableBody")],
    [P("Identity", "TableBody"), P("Cognito User Pools provide managed user sign-up/sign-in and JWT identity. Separate EC2/Lambda roles scope runtime access.", "TableBody"), P("User pool/client and frontend configuration deployed. End-to-end signup and token-protected flow not tested.", "TableBody")],
    [P("Monitoring/cost", "TableBody"), P("CloudWatch dashboard and alarms expose fleet, ALB, and Lambda behavior. AWS Budget raises early cost alerts.", "TableBody"), P("Dashboard, alarms, and $30 monthly alert deployed. Alert is not a spending cap. Billing history was unavailable.", "TableBody")],
    [P("AI/ML", "TableBody"), P("Bedrock generates listing-description assistance. SageMaker was intended for a trained category model.", "TableBody"), P("Bedrock is selected but real inference not tested. SageMaker disabled to preserve the reported $100 credits; categories use local suggestions.", "TableBody")],
]
story.append(table(service_rows, [0.88 * inch, 3.28 * inch, 2.89 * inch]))

story += [P("Verification results", "Section")]
checks = [
    [P("Check", "TableHead"), P("Observed result", "TableHead")],
    [P("Public frontend", "TableBody"), P("GET https://d39xic7jvhqh80.cloudfront.net returned HTTP 200 and served the Cognito-configured frontend bundle.", "TableBody")],
    [P("Public API health", "TableBody"), P("GET /api/health returned HTTP 200: app_mode=aws, auth_mode=cognito, database_backend=dynamodb, storage_backend=s3, description_provider=bedrock, category_provider=local, notification_backend=aws, warnings=[].", "TableBody")],
    [P("Load balancer", "TableBody"), P("Both targets were healthy before the user's subsequent manual stop. Current target health is not rechecked.", "TableBody")],
    [P("Auto Scaling group", "TableBody"), P("Desired capacity 2 and two healthy instances were observed before the user manually stopped one. The user reports no replacement; current state is unverified. An earlier refresh remained at 50% and was cancelled.", "TableBody")],
    [P("CloudFront cache", "TableBody"), P("Invalidation I477NMYV461VHHIHNWIVXLMFPN completed after publishing the rebuilt frontend.", "TableBody")],
    [P("Lambda", "TableBody"), P("Image processor reported Active. Invocation through a real image queue job was not verified.", "TableBody")],
]
story.append(table(checks, [1.55 * inch, 5.5 * inch]))
story += [P("What remains unverified", "Subsection")]
for item in [
    "Create and confirm a Cognito user, then exercise authenticated profile and listing flows.",
    "Create, update, search, and delete live DynamoDB listings; upload an image to S3 and observe the queued Lambda output.",
    "Confirm SNS email subscription and demonstrate delivery; make a real Bedrock inference request.",
    "Run a bounded load test and capture CPU-based scaling or a failure/replacement scenario.",
    "Capture the AWS Billing/Cost Explorer spend graph and budget screenshot. Cost Explorer access was denied to the active identity.",
    "Deploy a genuinely trained SageMaker model endpoint if credit permits; it is currently disabled.",
    "User reports the 5-8 minute demo video is recorded; add it to the submission. After grading, capture cleanup evidence showing billable resources terminated.",
]:
    story.append(P("- " + item))

story += [KeepTogether([
    P("Cost and operational controls", "Section"),
    P(
        "The deployed baseline is estimated at about $2-$3 per day before variable data transfer, NAT processing, ALB capacity units, logging, and AI inference. "
        "At published US East reference rates, a NAT Gateway is about $0.045/hour, an ALB base charge about $0.0225/hour, and a Linux t3.micro about $0.0104/hour. "
        "One NAT, one ALB, and two t3.micro instances total roughly $64/month at 730 hours, before other charges. These are estimates, not actual billed usage."
    ),
])]
story += [P(
    "The $30 monthly budget sends alerts at 80% and 100%; it does not stop resources and is not a guarantee that charges stay below $30. "
    "Cost Explorer was unavailable to the deployment identity, so actual spend and remaining credits could not be verified. SageMaker was left disabled. "
    "When the demo is no longer required, review and run Terraform destroy promptly to stop recurring NAT, ALB, and EC2 charges."
)]
story += [P("Pricing references", "Subsection")]
story += [P(
    "AWS pricing pages: <link href='https://aws.amazon.com/vpc/pricing/' color='#216E9B'>Amazon VPC</link>; "
    "<link href='https://aws.amazon.com/elasticloadbalancing/pricing/' color='#216E9B'>Elastic Load Balancing</link>; "
    "<link href='https://aws.amazon.com/ec2/instance-types/t3/' color='#216E9B'>T3 EC2 instances</link>. "
    "Rates vary by region and usage; values above are planning estimates.", "Tiny"
)]

story += [P("Rubric coverage and submission notes", "Section")]
rubric_rows = [
    [P("Rubric area", "TableHead"), P("Evidence in this submission", "TableHead"), P("Remaining gap", "TableHead")],
    [P("Phases 1-4: network, compute, storage, data", "TableBody"), P("Deployed infrastructure, live frontend/API, two healthy targets, architecture and service rationale.", "TableBody"), P("Authenticated CRUD, upload, load/failure evidence, and billing screenshot.", "TableBody")],
    [P("Phases 5-7: Lambda, messaging, identity", "TableBody"), P("Lambda active, queues and Cognito deployed; app health reports selected AWS backends.", "TableBody"), P("Real event processing, SNS delivery, and Cognito end-to-end flow.", "TableBody")],
    [P("Phase 8: DNS, monitoring, budget", "TableBody"), P("CloudWatch dashboard/alarms and a monthly budget alert are deployed.", "TableBody"), P("Route 53 custom name and billing evidence.", "TableBody")],
    [P("Phase 9: version control", "TableBody"), P("README, .gitignore, project source, deployment guide, and component-wise local commits with dates in the Nov 9-10 accommodation window.", "TableBody"), P("GitHub private repository and evaluator collaborator invite remain pending; push is deferred.", "TableBody")],
    [P("Phase 10: SageMaker and Bedrock", "TableBody"), P("Bedrock feature is configured; SageMaker infrastructure remains optional in Terraform.", "TableBody"), P("Real Bedrock call and trained/deployed SageMaker model are missing.", "TableBody")],
    [P("AI-DLC and report/demo", "TableBody"), P("AI-DLC log from available audit forward; this report and architecture diagram. User reports the demo video is recorded.", "TableBody"), P("Historical process cannot be reconstructed; video file and live component screenshots are not in this checkout.", "TableBody")],
]
story.append(table(rubric_rows, [1.36 * inch, 2.77 * inch, 2.92 * inch]))

story += [Spacer(1, 8), P("Version control note", "Subsection")]
story += [P(
    "The local component-wise commit history uses Nov 9-10, 2026 author and committer dates under the course-staff accommodation reported by the user. The commits were organized in this submission session; the history has not been pushed. "
    "The rubric requires a private GitHub repository and an accepted instructor/evaluator collaborator invitation; both remain pending."
)]
story += [P("Infrastructure cleanup", "Subsection")]
story += [P(
    "Terraform source is under infrastructure/terraform and keeps paid infrastructure disabled by default in checked-in variables. "
    "The active deployment depends on an ignored local terraform.tfvars and local state file; do not commit either. "
    "After grading, run a reviewed terraform destroy and retain a screenshot showing the billable resources are terminated."
)]

doc = SimpleDocTemplate(
    str(OUT), pagesize=letter, rightMargin=0.72 * inch, leftMargin=0.72 * inch,
    topMargin=0.62 * inch, bottomMargin=0.82 * inch,
    title="CampusConnect Cloud Project Report",
    author="CampusConnect Project Team",
    subject="CS-4075 Cloud Computing AWS deployment report",
)
doc.build(story, onFirstPage=footer, onLaterPages=footer)
print(OUT)
