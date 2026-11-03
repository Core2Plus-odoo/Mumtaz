"""Who is on the AI team page, and what each agent says.

Content lives here rather than in the template so a name, a specialty or a transcript
is one edit in one place. The transcripts are exactly the lines recorded in
static/src/audio/ai-team/<key>.mp3: if a transcript changes, the clip must be
re-recorded, or the text beside the player stops matching what it says.

Every agent is labelled AI on the page, and every claim here describes how the
faizy_ai add-on works: agents draft, a named person approves. Nothing here promises
a response time, a price or an outcome.
"""

AI_TEAM_GROUPS = [
    {
        "title": "Care and operations",
        "sub": "The agents behind every family's request.",
        "agents": [
            {
                "key": "rabta",
                "name": "Rabta",
                "title": "Customer Care AI",
                "tags": ["Urdu", "English"],
                "approver": "Mashood",
                "bullets": [
                    "Drafts WhatsApp replies",
                    "Turns requests into orders",
                    "Never gives medical advice",
                ],
                "transcript": "السلام علیکم! میں ربطہ ہوں، فیضی کی اے آئی کسٹمر کیئر ایجنٹ۔ میں آپ کے پیغامات کے جواب تیار کرتی ہوں، اور ہر جواب بھیجنے سے پہلے ہماری ٹیم کا کوئی فرد اسے منظور کرتا ہے۔",  # noqa: E501
            },
            {
                "key": "intezam",
                "name": "Intezam",
                "title": "Operations AI",
                "tags": ["Urdu", "English"],
                "approver": "Raza",
                "bullets": [
                    "Suggests who does each task",
                    "Chases photo proof",
                    "Keeps repairs with verified experts",
                ],
                "transcript": "السلام علیکم! میں انتظام ہوں، فیضی کا اے آئی آپریشنز ایجنٹ۔ میں تجویز کرتا ہوں کہ ہر کام کون کرے، اور کام کے بعد تصویری ثبوت کا انتظار رکھتا ہوں۔ حتمی منظوری ہماری آپریشنز ٹیم دیتی ہے۔",  # noqa: E501
            },
            {
                "key": "insights",
                "name": "Insights",
                "title": "Analytics AI",
                "tags": ["Urdu", "English"],
                "approver": "Umer, Mashood and Raza",
                "bullets": [
                    "Daily snapshot of every order",
                    "Flags overdue and unpaid",
                    "Spots plans about to lapse",
                ],
                "transcript": "السلام علیکم! میں انسائٹس ہوں، فیضی کی اے آئی تجزیاتی ایجنٹ۔ میں ہر روز بتاتی ہوں کہ کون سا آرڈر تاخیر کا شکار ہے، اور کون سا پلان ختم ہونے والا ہے۔",  # noqa: E501
            },
            {
                "key": "cos",
                "name": "Faizy CoS",
                "title": "Chief of Staff AI",
                "tags": ["Urdu", "English"],
                "approver": "Umer",
                "bullets": [
                    "Briefs Umer every morning",
                    "Names what is slipping",
                    "Drafts, never sends",
                ],
                "transcript": "السلام علیکم! میں فیضی کا چیف آف اسٹاف ہوں، ایک اے آئی ایجنٹ۔ ہر صبح میں بانی کو بریفنگ دیتا ہوں، اور صاف بتاتا ہوں کہ کیا پیچھے رہ رہا ہے۔",  # noqa: E501
            },
        ],
    },
    {
        "title": "Content crew",
        "sub": "The agents behind every post and reel.",
        "agents": [
            {
                "key": "noor",
                "name": "Noor",
                "title": "Content Strategy AI",
                "tags": ["Roman Urdu", "English"],
                "approver": "Mashood",
                "bullets": [
                    "Plans the week's posts and reels",
                    "Picks topics families care about",
                    "Keeps to the content brief",
                ],
                "transcript": "السلام علیکم! میں نور ہوں، فیضی کی اے آئی مواد کی حکمتِ عملی ایجنٹ۔ میں ہفتے بھر کی پوسٹس اور ریلز کا منصوبہ بناتی ہوں، اور ہر منصوبہ منظوری کے لیے ٹیم کو بھیجتی ہوں۔",  # noqa: E501
            },
            {
                "key": "kalam",
                "name": "Kalam",
                "title": "Scriptwriting AI",
                "tags": ["Roman Urdu", "English"],
                "approver": "Mashood",
                "bullets": [
                    "Writes warm, grounded scripts",
                    "Fact-checks every claim",
                    "Writes in Roman Urdu",
                ],
                "transcript": "السلام علیکم! میں قلم ہوں، فیضی کا اے آئی اسکرپٹ رائٹر۔ میں سادہ اور گرمجوش اسکرپٹ لکھتا ہوں، اور ہر دعوے کی تصدیق کرتا ہوں۔",  # noqa: E501
            },
            {
                "key": "tasveer",
                "name": "Tasveer",
                "title": "Visuals AI",
                "tags": ["Urdu", "English"],
                "approver": "Mashood",
                "bullets": [
                    "Storyboards every scene",
                    "Keeps characters consistent",
                    "Uses the locked brand look",
                ],
                "transcript": "السلام علیکم! میں تصویر ہوں، فیضی کی اے آئی ویژولز ایجنٹ۔ میں ہر منظر کا خاکہ بناتی ہوں، اور کرداروں کو ہر ویڈیو میں ایک جیسا رکھتی ہوں۔",  # noqa: E501
            },
            {
                "key": "awaaz",
                "name": "Awaaz",
                "title": "Voice AI",
                "tags": ["Urdu", "English"],
                "approver": "Mashood",
                "bullets": [
                    "Voices scripts in natural Urdu",
                    "Matches pitch to each line",
                    "Checks every line by ear",
                ],
                "transcript": "السلام علیکم! میں آواز ہوں، فیضی کا اے آئی وائس ایجنٹ۔ میں اسکرپٹس کو قدرتی اردو آواز دیتا ہوں، اور ہر لائن ٹیم کے سننے کے بعد ہی استعمال ہوتی ہے۔",  # noqa: E501
            },
            {
                "key": "jor",
                "name": "Jor",
                "title": "Edit and QC AI",
                "tags": ["Urdu", "English"],
                "approver": "Mashood",
                "bullets": [
                    "Cuts and subtitles reels",
                    "Checks brand, spelling and numbers",
                    "Flags anything off before QC",
                ],
                "transcript": "السلام علیکم! میں جوڑ ہوں، فیضی کا اے آئی ایڈیٹنگ اور کوالٹی ایجنٹ۔ میں ریلز جوڑتا ہوں، اور بھیجنے سے پہلے ہجے اور نمبر دوبارہ جانچتا ہوں۔",  # noqa: E501
            },
        ],
    },
]
