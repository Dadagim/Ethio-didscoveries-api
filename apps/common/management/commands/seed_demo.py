from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify

from apps.accounts.models import Profile, Tag
from apps.communities.models import Community, CommunityMembership
from apps.interactions.models import Comment, Reaction
from apps.knowledge.models import KnowledgeEntry, KnowledgeFolder
from apps.posts.models import Post

User = get_user_model()

PASSWORD = "SecurePass!2026"


def tags(*names):
    resolved = []
    for name in names:
        tag, _ = Tag.objects.get_or_create(
            slug=slugify(name),
            defaults={"name": name},
        )
        resolved.append(tag)
    return resolved


DEMO_USERS = [
    {
        "username": "amina",
        "email": "amina@etpm.test",
        "first_name": "Amina",
        "last_name": "Tesfaye",
        "profile": {
            "institution": "Addis Ababa University",
            "location": "Addis Ababa, Ethiopia",
            "bio": (
                "Engineering student exploring low-cost sensors for agriculture. "
                "Interested in how smallholder farmers can use simple technology to make better decisions."
            ),
            "interests": ["Agriculture", "Electronics", "Renewable energy"],
            "skills": ["Python", "Circuit design", "Data analysis"],
        },
    },
    {
        "username": "dawit",
        "email": "dawit@etpm.test",
        "first_name": "Dawit",
        "last_name": "Bekele",
        "profile": {
            "institution": "Addis Ababa Institute of Technology",
            "location": "Addis Ababa, Ethiopia",
            "bio": (
                "Electrical engineering student working on off-grid energy systems and practical "
                "maintenance models for rural infrastructure."
            ),
            "interests": ["Renewable energy", "Energy storage", "Micro-grids"],
            "skills": ["Circuit design", "MATLAB", "Field testing"],
        },
    },
    {
        "username": "hana",
        "email": "hana@etpm.test",
        "first_name": "Hana",
        "last_name": "Girma",
        "profile": {
            "institution": "Ethiopian Public Health Institute",
            "location": "Addis Ababa, Ethiopia",
            "bio": (
                "Public health researcher interested in how communities collect and use their own "
                "health data, especially where formal systems are thin."
            ),
            "interests": ["Public health", "Data ethics", "Community health"],
            "skills": ["Epidemiology", "Survey design", "R"],
        },
    },
    {
        "username": "yonas",
        "email": "yonas@etpm.test",
        "first_name": "Yonas",
        "last_name": "Alemu",
        "profile": {
            "institution": "Independent researcher",
            "location": "Bahir Dar, Ethiopia",
            "bio": (
                "Data scientist working on open tools for environmental monitoring and "
                "reproducible analysis."
            ),
            "interests": ["Data science", "Climate", "Open source"],
            "skills": ["Python", "Geospatial analysis", "Data visualisation"],
        },
    },
    {
        "username": "selam",
        "email": "selam@etpm.test",
        "first_name": "Selam",
        "last_name": "Tadesse",
        "profile": {
            "institution": "St. Daniel Secondary School",
            "location": "Addis Ababa, Ethiopia",
            "bio": (
                "Science teacher building inquiry-based lessons with limited laboratory equipment "
                "and a lot of curiosity."
            ),
            "interests": ["Science education", "Physics", "Teacher training"],
            "skills": ["Lesson design", "Demonstrations", "Assessment"],
        },
    },
]


COMMUNITIES = [
    {
        "name": "Renewable Energy Systems",
        "slug": "renewable-energy-systems",
        "owner": "amina",
        "category": Community.Category.DISCIPLINE,
        "visibility": Community.Visibility.PUBLIC,
        "purpose": "Make clean energy affordable for rural communities.",
        "description": (
            "A community for solar, wind, storage, and micro-grid research. We connect engineering "
            "students, technicians, and researchers working on practical clean-energy solutions for "
            "off-grid communities."
        ),
        "members": [("dawit", "member"), ("yonas", "member")],
    },
    {
        "name": "Public Health Data",
        "slug": "public-health-data",
        "owner": "hana",
        "category": Community.Category.PROBLEM,
        "visibility": Community.Visibility.RESTRICTED,
        "purpose": "Help communities collect and use health data responsibly.",
        "description": (
            "We discuss survey design, consent, data stewardship, and the practical ethics of "
            "community health data. Membership is reviewed so that conversations stay grounded in "
            "real field experience."
        ),
        "members": [("yonas", "member")],
    },
    {
        "name": "Smallholder Agriculture Technology",
        "slug": "smallholder-agriculture-technology",
        "owner": "amina",
        "category": Community.Category.PROBLEM,
        "visibility": Community.Visibility.PUBLIC,
        "purpose": "Build tools that work in real fields, not just laboratories.",
        "description": (
            "Low-cost sensing, irrigation, storage, and decision support for smallholder farms. "
            "Share field results, failures, and designs that others can reproduce."
        ),
        "members": [("dawit", "member"), ("selam", "member"), ("yonas", "moderator")],
    },
    {
        "name": "Learning Science & Teaching",
        "slug": "learning-science-teaching",
        "owner": "selam",
        "category": Community.Category.INSTITUTION,
        "visibility": Community.Visibility.PUBLIC,
        "purpose": "Make science teaching practical with limited resources.",
        "description": (
            "A space for teachers, teacher trainers, and researchers to exchange demonstrations, "
            "assessment ideas, and evidence about how students actually learn."
        ),
        "members": [("amina", "member")],
    },
]


POSTS = [
    {
        "community": "renewable-energy-systems",
        "author": "dawit",
        "type": Post.Type.QUESTION,
        "title": "How can we size a solar micro-grid for a rural clinic?",
        "content": (
            "We are designing a small solar micro-grid for a rural clinic that needs reliable power "
            "for refrigeration and lighting. The clinic has limited load data and no grid backup.\n\n"
            "We have estimated daily consumption at roughly 12 kWh but the peaks are unpredictable. "
            "What sizing method or rule of thumb would you recommend for battery capacity and panel "
            "rating, and what data should we collect first?"
        ),
        "tags": ["Solar", "Micro-grids", "Energy storage"],
        "comments": [
            (
                "amina",
                "Start by logging actual load for a week if possible. For a clinic, refrigeration "
                "duty cycle and evening lighting usually drive the peak. Size the battery for two "
                "cloudy days and keep a small generator as backup.",
            ),
            (
                "yonas",
                "If a week is too long, at least record the compressor start-up current. It is often "
                "the number that decides the inverter rating, not the daily energy total.",
            ),
        ],
        "reactions": [("amina", "insightful"), ("yonas", "helpful"), ("selam", "like")],
    },
    {
        "community": "renewable-energy-systems",
        "author": "amina",
        "type": Post.Type.PROBLEM,
        "title": "Battery replacements are failing earlier than expected in off-grid installations",
        "content": (
            "Across three installations we have observed lead-acid batteries failing after roughly "
            "18 months instead of the expected three years.\n\n"
            "The likely causes are deep discharge during cloudy periods and poor ventilation in the "
            "battery enclosure. We need a simple monitoring approach that local technicians can use "
            "without specialised equipment.\n\n"
            "What would you measure first, and what is the cheapest reliable way to measure it?"
        ),
        "tags": ["Batteries", "Maintenance", "Off-grid"],
        "comments": [
            (
                "dawit",
                "A shunt-based coulomb counter plus a temperature logger would give you most of the "
                "answer. The hard part is making the data readable for a technician who visits once a "
                "month.",
            ),
        ],
        "reactions": [("dawit", "insightful"), ("yonas", "like")],
    },
    {
        "community": "renewable-energy-systems",
        "author": "yonas",
        "type": Post.Type.RESEARCH,
        "title": "Field note: comparing measured and estimated load profiles for five clinics",
        "content": (
            "We instrumented five rural clinics for four weeks and compared measured load profiles "
            "with the estimates used at design time.\n\n"
            "Preliminary finding: daily energy estimates were within 15%, but peak demand was "
            "underestimated in four of five sites, sometimes by a factor of two. The gap came from "
            "compressor start-up and simultaneous evening loads.\n\n"
            "Next step is to publish the anonymised profiles and a simple sizing worksheet. Feedback "
            "on the method is welcome."
        ),
        "tags": ["Energy", "Field research", "Open data"],
        "comments": [
            (
                "amina",
                "This is exactly the evidence we need. Could the worksheet include a column for "
                "start-up current so the inverter sizing is not an afterthought?",
            ),
            (
                "yonas",
                "Yes. I will share a draft in this thread before publishing it.",
            ),
        ],
        "reactions": [("amina", "insightful"), ("dawit", "helpful")],
    },
    {
        "community": "smallholder-agriculture-technology",
        "author": "amina",
        "type": Post.Type.IDEA,
        "title": "A cheap soil-moisture sensor that farmers can repair themselves",
        "content": (
            "Most low-cost soil moisture sensors fail at the connector or the probe, not the "
            "electronics. What if we designed for repair from the start: screw terminals, a "
            "replaceable probe, and a calibration procedure that only needs a cup of water and dry "
            "soil?\n\n"
            "The goal is not laboratory accuracy. It is a reading that is consistent enough to "
            "support irrigation decisions and cheap enough to replace when it breaks."
        ),
        "tags": ["Agriculture", "Sensors", "Repair"],
        "comments": [
            (
                "selam",
                "This could be a strong school project too. Students could build and test the probe, "
                "then compare readings with a simple oven-dry method.",
            ),
            (
                "dawit",
                "Please share the connector choice. We have had good results with IP67 cable glands "
                "and ferrules in humid conditions.",
            ),
        ],
        "reactions": [("selam", "like"), ("dawit", "helpful"), ("yonas", "insightful")],
    },
    {
        "community": "smallholder-agriculture-technology",
        "author": "dawit",
        "type": Post.Type.PROJECT,
        "title": "Pilot: solar-powered irrigation controller for a 0.5 hectare plot",
        "content": (
            "We are testing a controller that runs a low-pressure drip system from a small solar "
            "array. The controller uses soil moisture and a simple schedule, with a manual override.\n\n"
            "Current status: prototype runs reliably, but the pump starts too often during cloudy "
            "afternoons. Next iteration will add a minimum rest period and a better state-of-charge "
            "estimate.\n\n"
            "Looking for feedback from anyone who has run similar pilots."
        ),
        "tags": ["Irrigation", "Solar", "Project"],
        "comments": [
            (
                "yonas",
                "How are you estimating state of charge? Voltage-only estimates drift badly under "
                "load. A coulomb counter may be worth the extra cost here.",
            ),
        ],
        "reactions": [("amina", "like"), ("yonas", "helpful")],
    },
    {
        "community": "public-health-data",
        "author": "hana",
        "type": Post.Type.DISCUSSION,
        "title": "What does informed consent look like when data is collected on paper?",
        "content": (
            "Many community health programmes still collect data on paper, then digitise it later. "
            "Consent forms are signed at the point of collection, but participants rarely see how "
            "the data is used afterwards.\n\n"
            "We are reviewing our process and would like examples of consent practices that are "
            "understandable, practical, and respectful—especially where literacy levels vary."
        ),
        "tags": ["Consent", "Data ethics", "Community health"],
        "comments": [
            (
                "yonas",
                "One approach we used was a short community report-back meeting before any dataset "
                "was shared externally. It is not a substitute for consent, but it closes the loop.",
            ),
        ],
        "reactions": [("yonas", "insightful")],
    },
    {
        "community": "public-health-data",
        "author": "yonas",
        "type": Post.Type.QUESTION,
        "title": "How small can a dataset be before it stops being useful?",
        "content": (
            "We are designing a monthly clinic indicator set. The temptation is to collect "
            "everything, but small facilities have limited staff time and the data quality drops "
            "quickly.\n\n"
            "How do you decide which indicators are worth the collection burden? I am looking for "
            "practical frameworks rather than general principles."
        ),
        "tags": ["Indicators", "Data quality", "Health systems"],
        "comments": [
            (
                "hana",
                "Start from the decisions the facility actually makes each month. If an indicator "
                "does not change a decision, it is a candidate for removal.",
            ),
        ],
        "reactions": [("hana", "helpful")],
    },
    {
        "community": "learning-science-teaching",
        "author": "selam",
        "type": Post.Type.PROBLEM,
        "title": "Demonstrations fail when students cannot see the small details",
        "content": (
            "Our physics demonstrations work for the front row and almost nobody else. A phone "
            "camera on a simple stand helps, but the projector is shared across the whole school.\n\n"
            "What low-cost setups have worked for showing small-scale phenomena to a full class?"
        ),
        "tags": ["Physics", "Demonstrations", "Classroom"],
        "comments": [
            (
                "amina",
                "For circuits, we built a large cardboard replica with oversized components and "
                "used it alongside the real circuit. Students could follow the current path, then "
                "look at the small version.",
            ),
        ],
        "reactions": [("amina", "helpful")],
    },
    {
        "community": "learning-science-teaching",
        "author": "amina",
        "type": Post.Type.RESEARCH,
        "title": "Small study: does peer explanation improve retention in science lessons?",
        "content": (
            "We ran a small classroom study comparing individual written revision with peer "
            "explanation followed by written revision. The peer-explanation group scored higher on "
            "a delayed quiz, but the sample is small and the groups were not randomly assigned.\n\n"
            "I am sharing the design and limitations because the result is suggestive, not "
            "conclusive. What would make this study stronger without disrupting the school year?"
        ),
        "tags": ["Education research", "Peer learning", "Assessment"],
        "comments": [
            (
                "selam",
                "Even with the limitations, this is useful for teachers. A stronger design might "
                "alternate the two conditions across topics within the same class.",
            ),
        ],
        "reactions": [("selam", "insightful")],
    },
]


KNOWLEDGE = [
    {
        "owner": "amina",
        "folder": "Sensors and agriculture",
        "description": "Field notes, sensor designs, and calibration ideas.",
        "entries": [
            {
                "title": "Capacitive soil moisture sensor: calibration notes",
                "content": (
                    "Dry soil reading: 2.1 V. Saturated soil reading: 1.2 V.\n\n"
                    "The relationship is not linear. For irrigation decisions, use three bands "
                    "(dry, okay, wet) rather than a precise percentage. Re-calibrate after changing "
                    "probe length or soil type."
                ),
                "source_url": "https://example.org/soil-moisture-calibration",
            },
            {
                "title": "Questions to ask before deploying a sensor",
                "content": (
                    "1. Who will maintain it when it fails?\n"
                    "2. What decision will the reading change?\n"
                    "3. Can the enclosure survive the rainy season?\n"
                    "4. Is there a manual fallback?\n"
                    "5. What data is stored, and who can see it?"
                ),
                "source_url": "",
            },
        ],
    },
    {
        "owner": "dawit",
        "folder": "Energy systems",
        "description": "Notes on solar, storage, and micro-grids.",
        "entries": [
            {
                "title": "Battery sizing for clinic micro-grids",
                "content": (
                    "For clinic micro-grids, start from measured daily load.\n\n"
                    "Rule of thumb heard from the community: size the battery for two cloudy days, "
                    "then check depth of discharge and round-trip efficiency. Panel rating should "
                    "cover daily load plus losses, with margin for the worst month."
                ),
                "source_url": "https://example.org/battery-sizing",
            },
            {
                "title": "Inverter sizing: do not forget start-up current",
                "content": (
                    "Daily energy and peak power are different problems. Refrigeration compressors "
                    "can draw several times their running current at start-up.\n\n"
                    "Before choosing an inverter, measure or obtain the start-up current for every "
                    "load that can start at the same time."
                ),
                "source_url": "",
            },
        ],
    },
    {
        "owner": "hana",
        "folder": "Research methods",
        "description": "Consent, sampling, and data stewardship.",
        "entries": [
            {
                "title": "Consent checklist for paper-based collection",
                "content": (
                    "Explain purpose in plain language.\n"
                    "Explain what is optional.\n"
                    "Explain who will see the data.\n"
                    "Provide a way to withdraw.\n"
                    "Record consent without collecting more identifiers than necessary."
                ),
                "source_url": "",
            },
        ],
    },
]


class Command(BaseCommand):
    help = "Create realistic Phase 1 demo data (idempotent)."

    def handle(self, *args, **options):
        users = self.create_users()
        communities = self.create_communities(users)
        self.create_posts(users, communities)
        self.create_knowledge(users)
        self.stdout.write(
            self.style.SUCCESS(
                "Demo data ready. Sign in with amina, dawit, hana, yonas, or selam "
                f"using password {PASSWORD}."
            )
        )

    def create_users(self):
        users = {}
        for spec in DEMO_USERS:
            user, created = User.objects.get_or_create(
                username=spec["username"],
                defaults={
                    "email": spec["email"],
                    "first_name": spec["first_name"],
                    "last_name": spec["last_name"],
                    "email_verified": True,
                },
            )
            if created:
                user.set_password(PASSWORD)
                user.save(update_fields=["password"])
            else:
                changed = []
                for field in ("email", "first_name", "last_name"):
                    if getattr(user, field) != spec[field]:
                        setattr(user, field, spec[field])
                        changed.append(field)
                if not user.email_verified:
                    user.email_verified = True
                    changed.append("email_verified")
                if changed:
                    user.save(update_fields=changed)

            profile, _ = Profile.objects.get_or_create(user=user)
            data = spec["profile"]
            profile.institution = data["institution"]
            profile.location = data["location"]
            profile.bio = data["bio"]
            profile.save()
            profile.interests.set(tags(*data["interests"]))
            profile.skills.set(tags(*data["skills"]))
            users[user.username] = user
        return users

    def create_communities(self, users):
        communities = {}
        for spec in COMMUNITIES:
            owner = users[spec["owner"]]
            community, created = Community.objects.get_or_create(
                slug=spec["slug"],
                defaults={
                    "name": spec["name"],
                    "description": spec["description"],
                    "purpose": spec["purpose"],
                    "category": spec["category"],
                    "visibility": spec["visibility"],
                    "owner": owner,
                },
            )
            if not created:
                community.name = spec["name"]
                community.description = spec["description"]
                community.purpose = spec["purpose"]
                community.category = spec["category"]
                community.visibility = spec["visibility"]
                community.owner = owner
                community.save()

            CommunityMembership.objects.get_or_create(
                community=community,
                user=owner,
                defaults={
                    "role": CommunityMembership.Role.OWNER,
                    "status": CommunityMembership.Status.ACTIVE,
                    "joined_at": timezone.now(),
                },
            )
            for username, role in spec["members"]:
                CommunityMembership.objects.get_or_create(
                    community=community,
                    user=users[username],
                    defaults={
                        "role": role,
                        "status": CommunityMembership.Status.ACTIVE,
                        "joined_at": timezone.now(),
                    },
                )
            communities[community.slug] = community
        return communities

    def create_posts(self, users, communities):
        for spec in POSTS:
            community = communities[spec["community"]]
            author = users[spec["author"]]
            post, created = Post.objects.get_or_create(
                community=community,
                author=author,
                title=spec["title"],
                defaults={"content": spec["content"], "type": spec["type"]},
            )
            if not created:
                continue
            post.tags.set(tags(*spec["tags"]))

            for username, body in spec.get("comments", []):
                Comment.objects.get_or_create(
                    post=post,
                    author=users[username],
                    body=body,
                )
            for username, reaction_type in spec.get("reactions", []):
                Reaction.objects.get_or_create(
                    post=post,
                    user=users[username],
                    defaults={"type": reaction_type},
                )

    def create_knowledge(self, users):
        for spec in KNOWLEDGE:
            owner = users[spec["owner"]]
            folder, _ = KnowledgeFolder.objects.get_or_create(
                owner=owner,
                name=spec["folder"],
                defaults={"description": spec["description"]},
            )
            for entry in spec["entries"]:
                KnowledgeEntry.objects.get_or_create(
                    owner=owner,
                    folder=folder,
                    title=entry["title"],
                    defaults={
                        "content": entry["content"],
                        "source_url": entry["source_url"],
                    },
                )
