import random


class TextGenerator:
    """Synthetic business-mail text from small hand-written word lists (no third-party text)."""

    first_names = (
        "Alex", "Ana", "Ben", "Birgit", "Carla", "Chen", "Daniel", "Dilara", "Elena", "Emil", "Fatima", "Felix",
        "Greta", "Hannah", "Hiro", "Ines", "Jonas", "Jürgen", "Kai", "Lea", "Lukas", "Maja", "Marco", "Mehmet",
        "Nora", "Olga", "Oskar", "Paula", "Priya", "Quentin", "Rosa", "Samir", "Sophie", "Tariq", "Tobias", "Ula",
        "Valentin", "Wiebke", "Xenia", "Yusuf", "Zoë", "Amara", "Bruno", "Clara", "Dmitri", "Eva", "Frida", "Gabriel",
    )
    last_names = (
        "Albers", "Bauer", "Castillo", "Demir", "Eriksen", "Fischer", "García", "Hoffmann", "Ivanova", "Jansen",
        "Kowalski", "Lehmann", "Moreau", "Nakamura", "Okafor", "Petrov", "Quast", "Rossi", "Schulz", "Tanaka",
        "Ulrich", "Vogel", "Weber", "Xu", "Yilmaz", "Zimmermann", "Brandt", "Costa", "Dąbrowski", "Engel", "Franke",
        "Graf", "Haas", "Iversen", "Jung", "Keller", "Lindqvist", "Müller", "Novak", "Ortega",
    )
    domains = ("example.com", "example.org", "example.net", "mail.example.com", "corp.example.org",
               "lab.example.net", "shop.example.com", "team.example.org")
    topics = (
        "budget", "roadmap", "release", "invoice", "contract", "workshop", "offsite", "hiring", "onboarding",
        "migration", "audit", "newsletter", "quarterly report", "price list", "travel plan", "kick-off",
        "maintenance window", "customer feedback", "design review", "status update", "partner meeting",
        "training", "inventory", "warehouse move", "server upgrade", "trade fair", "annual planning",
    )
    subject_patterns = (
        "{Topic} for {month}", "Question about the {topic}", "{Topic}: next steps", "Draft {topic} attached",
        "Updated {topic}", "Reminder: {topic} on {weekday}", "{Topic} – please review", "Notes from the {topic}",
        "{Topic} {year}", "Quick question", "Re-scheduling the {topic}", "Final version of the {topic}",
        "{Topic} numbers", "Feedback on the {topic}", "Agenda for {weekday}",
    )
    months = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
              "November", "December")
    weekdays = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")
    openers = ("Hi {name},", "Hello {name},", "Dear {name},", "Good morning {name},", "Hi all,", "Hello team,")
    closers = ("Best regards,", "Thanks,", "Kind regards,", "Cheers,", "Many thanks,", "Best,")
    subjects = ("the team", "our group", "the vendor", "the customer", "finance", "the board", "marketing",
                "the project office", "support", "the new colleague", "legal", "the agency", "operations")
    verbs = ("reviewed", "updated", "approved", "moved", "postponed", "shared", "prepared", "finished", "checked",
             "discussed", "sent", "planned", "confirmed", "rewrote", "simplified", "collected")
    objects = ("the numbers", "the schedule", "the slides", "the draft", "the spreadsheet", "the open points",
               "the timeline", "the figures for last month", "the checklist", "the list of risks", "the estimate",
               "the room booking", "the latest version", "the summary", "the order", "the test results")
    tails = ("before Friday", "by the end of the week", "for the next meeting", "as discussed", "yesterday",
             "this morning", "in the shared folder", "with a few small changes", "after the call",
             "in more detail", "for the second quarter", "together with the agency", "without further changes")
    asks = ("Could you have a look", "Can you confirm", "Please let me know", "Would it be possible to check",
            "Do you have time to go through it", "Could you send me your comments", "Can we talk about it")

    def __init__(self, rng: random.Random):
        self.rng = rng

    def person(self) -> tuple[str, str]:
        first = self.rng.choice(self.first_names)
        last = self.rng.choice(self.last_names)
        local = f"{self.ascii(first)}.{self.ascii(last)}".lower()
        return f"{first} {last}", f"{local}@{self.rng.choice(self.domains)}"

    @staticmethod
    def ascii(text: str) -> str:
        table = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss", "é": "e", "ë": "e", "í": "i",
                               "ą": "a", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue"})
        return text.translate(table)

    def subject(self, year: int) -> str:
        topic = self.rng.choice(self.topics)
        return self.rng.choice(self.subject_patterns).format(
            topic=topic, Topic=topic[0].upper() + topic[1:], month=self.rng.choice(self.months),
            weekday=self.rng.choice(self.weekdays), year=year)

    def sentence(self) -> str:
        kind = self.rng.random()
        if kind < 0.55:
            text = (f"{self.rng.choice(self.subjects).capitalize()} {self.rng.choice(self.verbs)} "
                    f"{self.rng.choice(self.objects)} {self.rng.choice(self.tails)}.")
        elif kind < 0.8:
            text = f"{self.rng.choice(self.asks)} at {self.rng.choice(self.objects)} {self.rng.choice(self.tails)}?"
        else:
            text = (f"We {self.rng.choice(self.verbs)} {self.rng.choice(self.objects)}, and "
                    f"{self.rng.choice(self.subjects)} {self.rng.choice(self.verbs)} {self.rng.choice(self.objects)}.")
        return text

    def paragraphs(self, count: int) -> list[str]:
        return [" ".join(self.sentence() for _ in range(self.rng.randint(2, 6))) for _ in range(count)]

    def body(self, recipient_first_name: str, sender_name: str, paragraph_count: int,
             planted: list[str]) -> list[str]:
        paragraphs = self.paragraphs(paragraph_count)
        for term in planted:
            i = self.rng.randrange(len(paragraphs))
            paragraphs[i] += f" The {term} item is still open."
        opener = self.rng.choice(self.openers).format(name=recipient_first_name)
        return [opener, *paragraphs, f"{self.rng.choice(self.closers)}\n{sender_name}"]
