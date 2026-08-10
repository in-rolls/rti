"""The parts of an application that never change, defined once per language.

Every letter opens the same way, cites the same fee and the same deadline, makes
the same offer to clarify, and closes the same way. Only the numbered asks
differ, and those live in `bodies.py`. Before this split, three English letters
and three Hindi letters each carried their own copy of this text, so a change to
the fee sentence meant six edits and usually got four.

Text is written unwrapped. `compose.py` wraps it, so a translator never has to
think about line breaks.
"""

from __future__ import annotations

STRINGS: dict[str, dict[str, str]] = {
    # ----------------------------------------------------------------- English
    "en": {
        "to_line": "To\nThe Public Information Officer (under the Right to Information Act, 2005),",
        "date_label": "Date",
        "subject_label": "Subject",
        "subject": (
            "Request for information under Section 6(1) of the Right to Information " "Act, 2005"
        ),
        "salutation": "Respected Sir/Madam,",
        "fee_clause": (
            "I am a citizen of India, and the prescribed application fee of Rs. {fee} "
            "has been paid; proof of payment accompanies this application."
        ),
        "transfer_clause": (
            "If any part of this request concerns another public authority, I would be "
            "grateful if it were transferred under Section 6(3) and if I were informed "
            "of the transfer."
        ),
        "clarify_clause": (
            "Should anything in this request be unclear, I would gladly clarify it on "
            "the contact details below, rather than have the application returned."
        ),
        "deadline_clause": (
            "I would be grateful to receive the information within {statutory_days} "
            "days, as provided under Section 7(1)."
        ),
        "thanks": "Thank you for your time.",
        "sign_off": "Yours faithfully,",
        "phone_label": "Phone",
        "email_label": "Email",
    },
    # ------------------------------------------------------------------- Hindi
    "hi": {
        "to_line": "सेवा में\nजन सूचना अधिकारी (सूचना का अधिकार अधिनियम, 2005 के अंतर्गत),",
        "date_label": "दिनांक",
        "subject_label": "विषय",
        "subject": ("सूचना का अधिकार अधिनियम, 2005 की धारा 6(1) के अंतर्गत सूचना हेतु आवेदन"),
        "salutation": "महोदय/महोदया,",
        "fee_clause": (
            "मैं भारत का नागरिक हूँ तथा निर्धारित आवेदन शुल्क रु. {fee} का भुगतान कर "
            "दिया गया है; भुगतान का प्रमाण इस आवेदन के साथ संलग्न है।"
        ),
        "transfer_clause": (
            "यदि इस आवेदन का कोई भाग किसी अन्य लोक प्राधिकरण से संबंधित हो, तो कृपया "
            "उसे धारा 6(3) के अंतर्गत अंतरित कर मुझे सूचित करने की कृपा करें।"
        ),
        "clarify_clause": (
            "यदि इस आवेदन में कुछ भी अस्पष्ट हो, तो आवेदन लौटाने के स्थान पर कृपया "
            "नीचे दिए गए संपर्क विवरण पर सूचित करें; मैं सहर्ष स्पष्ट कर दूँगा/दूँगी।"
        ),
        "deadline_clause": (
            "कृपया धारा 7(1) के अनुसार {statutory_days} दिनों के भीतर सूचना उपलब्ध "
            "कराने की कृपा करें।"
        ),
        "thanks": "आपके सहयोग हेतु धन्यवाद।",
        "sign_off": "भवदीय/भवदीया,",
        "phone_label": "दूरभाष",
        "email_label": "ईमेल",
    },
    # ------------------------------------------------------------------- Tamil
    "ta": {
        "to_line": "பெறுநர்\nபொது தகவல் அலுவலர் (தகவல் அறியும் உரிமைச் சட்டம், 2005-ன் கீழ்),",
        "date_label": "நாள்",
        "subject_label": "பொருள்",
        "subject": (
            "தகவல் அறியும் உரிமைச் சட்டம், 2005-ன் பிரிவு 6(1)-ன் கீழ் தகவல் கோரி " "விண்ணப்பம்"
        ),
        "salutation": "ஐயா/அம்மையீர்,",
        "fee_clause": (
            "நான் இந்தியக் குடிமகன் ஆவேன். நிர்ணயிக்கப்பட்ட விண்ணப்பக் கட்டணம் ரூ. "
            "{fee} செலுத்தப்பட்டுள்ளது; செலுத்தியதற்கான சான்று இத்துடன் இணைக்கப்பட்டுள்ளது."
        ),
        "transfer_clause": (
            "இந்த விண்ணப்பத்தின் ஏதேனும் ஒரு பகுதி வேறு ஒரு பொது அதிகார அமைப்பைச் "
            "சார்ந்ததாக இருப்பின், அதைப் பிரிவு 6(3)-ன் கீழ் மாற்றி அனுப்பி, அது குறித்து "
            "எனக்குத் தெரிவிக்குமாறு தாழ்மையுடன் கேட்டுக்கொள்கிறேன்."
        ),
        "clarify_clause": (
            "இந்த விண்ணப்பத்தில் ஏதேனும் தெளிவற்று இருப்பின், விண்ணப்பத்தைத் திருப்பி "
            "அனுப்பாமல், கீழே உள்ள தொடர்பு விவரங்களில் தெரிவித்தால் நான் மகிழ்ச்சியுடன் "
            "விளக்கம் அளிப்பேன்."
        ),
        "deadline_clause": (
            "பிரிவு 7(1)-ன் படி {statutory_days} நாட்களுக்குள் தகவலை வழங்குமாறு "
            "தாழ்மையுடன் கேட்டுக்கொள்கிறேன்."
        ),
        "thanks": "தங்கள் நேரத்திற்கு நன்றி.",
        "sign_off": "தங்கள் உண்மையுள்ள,",
        "phone_label": "தொலைபேசி",
        "email_label": "மின்னஞ்சல்",
    },
    # ------------------------------------------------------------------ Telugu
    "te": {
        "to_line": "స్వీకర్త\nప్రజా సమాచార అధికారి (సమాచార హక్కు చట్టం, 2005 కింద),",
        "date_label": "తేదీ",
        "subject_label": "విషయం",
        "subject": "సమాచార హక్కు చట్టం, 2005 సెక్షన్ 6(1) కింద సమాచారం కోరుతూ దరఖాస్తు",
        "salutation": "గౌరవనీయులైన అయ్యా/అమ్మా,",
        "fee_clause": (
            "నేను భారత పౌరుడను/పౌరురాలిని. నిర్ణీత దరఖాస్తు రుసుము రూ. {fee} "
            "చెల్లించడమైనది; చెల్లింపు రుజువు ఈ దరఖాస్తుతో జతపరచబడినది."
        ),
        "transfer_clause": (
            "ఈ దరఖాస్తులోని ఏదైనా భాగం మరొక ప్రజా అధికార సంస్థకు సంబంధించినదైతే, దానిని "
            "సెక్షన్ 6(3) కింద బదిలీ చేసి, ఆ విషయాన్ని నాకు తెలియజేయవలసినదిగా "
            "మనవి చేసుకుంటున్నాను."
        ),
        "clarify_clause": (
            "ఈ దరఖాస్తులో ఏదైనా అస్పష్టంగా ఉంటే, దరఖాస్తును తిప్పి పంపే బదులు కింద "
            "ఇచ్చిన వివరాలకు తెలియజేయగలరు; నేను సంతోషంగా వివరణ ఇస్తాను."
        ),
        "deadline_clause": (
            "సెక్షన్ 7(1) ప్రకారం {statutory_days} రోజులలోపు సమాచారాన్ని అందించవలసినదిగా " "మనవి."
        ),
        "thanks": "మీ సమయానికి ధన్యవాదాలు.",
        "sign_off": "మీ విధేయుడు/విధేయురాలు,",
        "phone_label": "ఫోన్",
        "email_label": "ఇమెయిల్",
    },
    # ----------------------------------------------------------------- Kannada
    "kn": {
        "to_line": "ಗೆ\nಸಾರ್ವಜನಿಕ ಮಾಹಿತಿ ಅಧಿಕಾರಿ (ಮಾಹಿತಿ ಹಕ್ಕು ಅಧಿನಿಯಮ, 2005ರ ಅಡಿಯಲ್ಲಿ),",
        "date_label": "ದಿನಾಂಕ",
        "subject_label": "ವಿಷಯ",
        "subject": "ಮಾಹಿತಿ ಹಕ್ಕು ಅಧಿನಿಯಮ, 2005ರ ಕಲಂ 6(1)ರ ಅಡಿಯಲ್ಲಿ ಮಾಹಿತಿ ಕೋರಿ ಅರ್ಜಿ",
        "salutation": "ಮಾನ್ಯರೇ,",
        "fee_clause": (
            "ನಾನು ಭಾರತದ ಪ್ರಜೆಯಾಗಿದ್ದೇನೆ. ನಿಗದಿತ ಅರ್ಜಿ ಶುಲ್ಕ ರೂ. {fee} ಪಾವತಿಸಲಾಗಿದೆ; "
            "ಪಾವತಿಯ ದಾಖಲೆಯನ್ನು ಈ ಅರ್ಜಿಯೊಂದಿಗೆ ಲಗತ್ತಿಸಲಾಗಿದೆ."
        ),
        "transfer_clause": (
            "ಈ ಅರ್ಜಿಯ ಯಾವುದೇ ಭಾಗವು ಬೇರೊಂದು ಸಾರ್ವಜನಿಕ ಪ್ರಾಧಿಕಾರಕ್ಕೆ ಸಂಬಂಧಿಸಿದ್ದರೆ, ಅದನ್ನು "
            "ಕಲಂ 6(3)ರ ಅಡಿಯಲ್ಲಿ ವರ್ಗಾಯಿಸಿ ಆ ಬಗ್ಗೆ ನನಗೆ ತಿಳಿಸಬೇಕಾಗಿ ವಿನಂತಿಸುತ್ತೇನೆ."
        ),
        "clarify_clause": (
            "ಈ ಅರ್ಜಿಯಲ್ಲಿ ಏನಾದರೂ ಅಸ್ಪಷ್ಟವಾಗಿದ್ದರೆ, ಅರ್ಜಿಯನ್ನು ಹಿಂದಿರುಗಿಸುವ ಬದಲು ಕೆಳಗಿನ "
            "ಸಂಪರ್ಕ ವಿವರಗಳಿಗೆ ತಿಳಿಸಿದರೆ ನಾನು ಸಂತೋಷದಿಂದ ಸ್ಪಷ್ಟಪಡಿಸುತ್ತೇನೆ."
        ),
        "deadline_clause": (
            "ಕಲಂ 7(1)ರ ಪ್ರಕಾರ {statutory_days} ದಿನಗಳ ಒಳಗೆ ಮಾಹಿತಿಯನ್ನು ಒದಗಿಸಬೇಕಾಗಿ "
            "ವಿನಂತಿಸುತ್ತೇನೆ."
        ),
        "thanks": "ತಮ್ಮ ಸಮಯಕ್ಕೆ ಧನ್ಯವಾದಗಳು.",
        "sign_off": "ತಮ್ಮ ವಿಶ್ವಾಸಿ,",
        "phone_label": "ದೂರವಾಣಿ",
        "email_label": "ಇಮೇಲ್",
    },
    # ----------------------------------------------------------------- Marathi
    "mr": {
        "to_line": "प्रति\nजन माहिती अधिकारी (माहितीचा अधिकार अधिनियम, 2005 अंतर्गत),",
        "date_label": "दिनांक",
        "subject_label": "विषय",
        "subject": "माहितीचा अधिकार अधिनियम, 2005 च्या कलम 6(1) अंतर्गत माहिती मिळणेबाबत अर्ज",
        "salutation": "महोदय/महोदया,",
        "fee_clause": (
            "मी भारताचा नागरिक आहे. विहित अर्ज शुल्क रु. {fee} भरण्यात आले असून, "
            "भरणा केल्याचा पुरावा या अर्जासोबत जोडला आहे."
        ),
        "transfer_clause": (
            "या अर्जाचा कोणताही भाग अन्य लोक प्राधिकरणाशी संबंधित असल्यास, तो कलम 6(3) "
            "अंतर्गत हस्तांतरित करून मला कळविण्याची कृपा करावी."
        ),
        "clarify_clause": (
            "या अर्जातील काही बाब अस्पष्ट असल्यास, अर्ज परत पाठविण्याऐवजी खालील संपर्क "
            "तपशिलावर कळवावे; मी आनंदाने खुलासा करेन."
        ),
        "deadline_clause": (
            "कलम 7(1) नुसार {statutory_days} दिवसांच्या आत माहिती उपलब्ध करून देण्याची "
            "कृपा करावी."
        ),
        "thanks": "आपल्या वेळेबद्दल धन्यवाद.",
        "sign_off": "आपला/आपली विश्वासू,",
        "phone_label": "दूरध्वनी",
        "email_label": "ईमेल",
    },
}

DRAFT_BANNER = """\
{rule}
DRAFT TRANSLATION - DO NOT FILE YET

The {language} text below has not been checked by a native speaker. Have it
reviewed, then delete this banner before pasting anything into the portal.
{rule}"""

ENGLISH_COPY_HEADER = "ENGLISH COPY (for reference; the application above is the one filed)"


def strings(language: str) -> dict[str, str]:
    """Fixed text for a language, falling back to English if it is unwritten."""
    return STRINGS.get(language, STRINGS["en"])
