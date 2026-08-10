"""Every controlled vocabulary in the study, defined exactly once.

Three things are generated from this module and must never drift apart: the
``CHECK`` constraints in ``schema.sql``, the option lists of the two Google Forms
that research assistants fill, and the validator behind ``rti-check``. Adding an
event type here adds it to all three.
"""

from __future__ import annotations

# --------------------------------------------------------------------------
# Design
# --------------------------------------------------------------------------

TOPICS = ("rti_meta", "attendance", "financial")
"""What a letter asks for. `rti_meta` is the primary ask; the other two are
fallbacks used when a batch deliberately varies the request."""

TOPIC_LABELS = {
    "rti_meta": "RTI register for the last 12 months",
    "attendance": "Sanctioned strength and attendance on a date",
    "financial": "Budget allocated against expenditure, two financial years",
}

LANGUAGES = ("en", "hi", "ta", "te", "kn", "mr")

LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "ta": "Tamil",
    "te": "Telugu",
    "kn": "Kannada",
    "mr": "Marathi",
}

REVIEWED_LANGUAGES = frozenset({"en", "hi"})
"""Languages whose letter text a native speaker has signed off on. Anything
outside this set renders with a banner telling the RA not to file it yet."""

CHANNELS = ("portal", "post")

# --------------------------------------------------------------------------
# Filing
# --------------------------------------------------------------------------

FILING_OUTCOMES = ("filed", "not_filed")

NOT_FILED_REASONS = (
    "authority_not_listed",
    "portal_down",
    "login_failed",
    "otp_not_received",
    "captcha_failed",
    "payment_failed",
    "authority_abolished",
    "address_invalid",
    "duplicate_of_other_application",
    "dropped_by_design",
    "other",
)
"""Why a sampled office never became a filed application.

This is the study's attrition record. An application row exists from the moment
the office is sampled, so a failure here is visible in December; a filing log
that only records successes loses it the same afternoon.
"""

NOT_FILED_REASON_LABELS = {
    "authority_not_listed": "The office is not in the portal's dropdown",
    "portal_down": "Portal unreachable after three attempts",
    "login_failed": "Could not log in",
    "otp_not_received": "OTP never arrived",
    "captcha_failed": "CAPTCHA could not be solved",
    "payment_failed": "Payment gateway failed",
    "authority_abolished": "Office abolished or merged",
    "address_invalid": "No usable postal address",
    "duplicate_of_other_application": "Same office already covered by another application",
    "dropped_by_design": "Dropped deliberately by the researchers",
    "other": "Something else (explain in notes)",
}

PAYMENT_MODES = ("online", "ipo", "dd", "court_fee_stamp", "cash", "bpl_exempt", "not_paid")

PAYMENT_MODE_LABELS = {
    "online": "Online (net banking, UPI, card)",
    "ipo": "Indian Postal Order",
    "dd": "Demand draft",
    "court_fee_stamp": "Court fee stamp",
    "cash": "Cash at the counter",
    "bpl_exempt": "Exempt (below poverty line)",
    "not_paid": "Not paid",
}

# --------------------------------------------------------------------------
# Monitoring
# --------------------------------------------------------------------------

EVENT_TYPES = (
    "acknowledgment",
    "transfer_6_3",
    "fee_demand",
    "clarification_demand",
    "id_demand",
    "personal_contact",
    "interim_reply",
    "response_received",
    "denial",
    "returned_undelivered",
    "reminder_sent",
    "first_appeal_filed",
    "first_appeal_decided",
    "second_appeal_filed",
    "hearing_notice",
    "second_appeal_decided",
    "note",
)
"""One row per thing that happened to an application, in the order it happened.

Deliberately excludes anything derivable. There is no `deemed_refusal` event
because deemed refusal is the *absence* of a response by the statutory deadline,
and an RA should never be asked to record a non-event.
"""

EVENT_TYPE_LABELS = {
    "acknowledgment": "Acknowledgement received",
    "transfer_6_3": "Transferred to another office under s.6(3)",
    "fee_demand": "Further fee demanded",
    "clarification_demand": "Clarification demanded",
    "id_demand": "Proof of citizenship or identity demanded",
    "personal_contact": "PIO telephoned or asked me to come in person",
    "interim_reply": "Interim or holding reply",
    "response_received": "Substantive reply received",
    "denial": "Information refused",
    "returned_undelivered": "Letter came back undelivered",
    "reminder_sent": "Reminder sent by us",
    "first_appeal_filed": "First appeal filed",
    "first_appeal_decided": "First appeal decided",
    "second_appeal_filed": "Second appeal filed",
    "hearing_notice": "Hearing notice received",
    "second_appeal_decided": "Second appeal decided",
    "note": "Something else worth recording",
}

MEDIUMS = ("portal", "email", "post", "speed_post", "phone", "in_person")

MEDIUM_LABELS = {
    "portal": "On the RTI portal",
    "email": "By email",
    "post": "By ordinary post",
    "speed_post": "By Speed Post or registered post",
    "phone": "By telephone",
    "in_person": "In person",
}

DIRECTIONS = ("inbound", "outbound")

# Events we send rather than receive. Used to default the `direction` column so
# an RA never has to think about it.
OUTBOUND_EVENT_TYPES = frozenset({"reminder_sent", "first_appeal_filed", "second_appeal_filed"})


ALL_LABELS = (
    EVENT_TYPE_LABELS,
    NOT_FILED_REASON_LABELS,
    MEDIUM_LABELS,
    PAYMENT_MODE_LABELS,
)
"""Every human-facing label the Google Forms show.

`rti-forms` renders these into the forms and `rti-load` maps them back to the
stored value. Keeping both ends of that round trip in one place is what stops a
reworded option from becoming a value the schema rejects.
"""


def sql_check(column: str, values: tuple[str, ...], allow_blank: bool = True) -> str:
    """A SQL CHECK constraint over a controlled vocabulary.

    Blank stays legal by default because most of these columns are filled later,
    by a research assistant, and "not recorded yet" is a state the study needs to
    be able to represent.
    """
    joined = ", ".join(f"'{v}'" for v in values)
    if allow_blank:
        return f"CHECK ({column} = '' OR {column} IN ({joined}))"
    return f"CHECK ({column} IN ({joined}))"
