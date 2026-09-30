"""Author a curated harder Hindi/English problem set with verified gold answers.

Every gold answer is checked against an independent re-derivation in this
script, so a record is only emitted if the arithmetic is consistent. The Hindi
translations are flagged translation_reviewed=False and must pass the same
review gate (pilot_translation_audit.csv) used for the legacy pilot before any
collection happens.
"""

from __future__ import annotations

import csv
from pathlib import Path

PROBLEMS: list[dict[str, str]] = [
    {
        "problem_id": "hard-001",
        "answer": "21",
        "domain": "shopping",
        "problem_en": (
            "A stationery shop sells pens for $2 each and notebooks for $5 each. "
            "Priya bought 4 pens and 3 notebooks and used a $2 coupon on the whole purchase. "
            "How many dollars did she pay in total?"
        ),
    },
    {
        "problem_id": "hard-002",
        "answer": "70",
        "domain": "speed",
        "problem_en": (
            "A train traveled 60 miles per hour for 2 hours, then 90 miles per hour for the next hour. "
            "What was its average speed in miles per hour over the whole trip?"
        ),
    },
    {
        "problem_id": "hard-003",
        "answer": "34",
        "domain": "business",
        "problem_en": (
            "A fruit vendor bought 2 kilograms of apples at $4 per kilogram and 3 kilograms of oranges "
            "at $3 per kilogram. He sold all of it for 200% of what he paid. How many dollars did he receive?"
        ),
    },
    {
        "problem_id": "hard-004",
        "answer": "2",
        "domain": "work_rate",
        "problem_en": (
            "Hose A fills a tank in 6 hours and Hose B fills the same tank in 3 hours. "
            "If both hoses are opened together, how many hours will it take to fill the tank?"
        ),
    },
    {
        "problem_id": "hard-005",
        "answer": "32",
        "domain": "age",
        "problem_en": (
            "Sara is twice as old as Ravi. In six years, the sum of their ages will be 60. "
            "How old is Sara now?"
        ),
    },
    {
        "problem_id": "hard-006",
        "answer": "300",
        "domain": "book",
        "problem_en": (
            "Neha read 20 pages on the first day and doubled the number of pages she read each "
            "following day for the next three days. How many pages did she read in total over the four days?"
        ),
    },
    {
        "problem_id": "hard-007",
        "answer": "10",
        "domain": "geometry",
        "problem_en": (
            "A rectangle's length is 8 centimeters more than its width, and its perimeter is 56 centimeters. "
            "How many centimeters wide is the rectangle?"
        ),
    },
    {
        "problem_id": "hard-008",
        "answer": "240",
        "domain": "sharing",
        "problem_en": (
            "Three friends bought a gift. Pooja paid one-half of the cost, Anjali paid one-third, "
            "and Reena paid the remaining $40. How many dollars did the gift cost?"
        ),
    },
    {
        "problem_id": "hard-009",
        "answer": "38",
        "domain": "sequence",
        "problem_en": (
            "The sum of three consecutive even numbers is 108. What is the largest of the three numbers?"
        ),
    },
    {
        "problem_id": "hard-010",
        "answer": "48",
        "domain": "discount",
        "problem_en": (
            "A jacket costs $80. The shop first discounts it by 25%, then takes an additional 20% "
            "off the already reduced price. How many dollars is the final price?"
        ),
    },
    {
        "problem_id": "hard-011",
        "answer": "60",
        "domain": "speed",
        "problem_en": (
            "Amit and Ben start 100 miles apart and walk toward each other, Amit at 20 miles per hour "
            "and Ben at 30 miles per hour. How many miles will Ben have walked when they meet?"
        ),
    },
    {
        "problem_id": "hard-012",
        "answer": "40",
        "domain": "fraction",
        "problem_en": (
            "A fruit seller started with 120 apples. He sold one-third of them in the morning, "
            "then sold half of the remaining apples in the afternoon. How many apples were left at the end?"
        ),
    },
    {
        "problem_id": "hard-013",
        "answer": "5",
        "domain": "tickets",
        "problem_en": (
            "Riya bought 5 adult tickets at $12 each for a show and also bought some child tickets "
            "at $8 each. She paid $100 in total. How many child tickets did she buy?"
        ),
    },
    {
        "problem_id": "hard-014",
        "answer": "35",
        "domain": "average",
        "problem_en": (
            "The average of four numbers is 25. Three of the numbers are 20, 30, and 15. "
            "What is the fourth number?"
        ),
    },
    {
        "problem_id": "hard-015",
        "answer": "5",
        "domain": "work_rate",
        "problem_en": (
            "Machine A produces 12 toys per hour and Machine B produces 8 toys per hour. "
            "Working together, how many hours will they need to produce 100 toys?"
        ),
    },
    {
        "problem_id": "hard-016",
        "answer": "75",
        "domain": "business",
        "problem_en": (
            "Karan bought a bag for $60 and sold it for a 25% profit. "
            "How many dollars did he sell it for?"
        ),
    },
    {
        "problem_id": "hard-017",
        "answer": "10",
        "domain": "fraction",
        "problem_en": (
            "A 5-meter rope was cut into 4 equal pieces per meter. Half of all the pieces were "
            "later discarded. How many pieces were kept?"
        ),
    },
    {
        "problem_id": "hard-018",
        "answer": "130",
        "domain": "inventory",
        "problem_en": (
            "A shop had 200 notebooks. It sold three-fifths of them and then received a delivery "
            "of 50 more notebooks. How many notebooks does the shop have now?"
        ),
    },
    {
        "problem_id": "hard-019",
        "answer": "6",
        "domain": "speed",
        "problem_en": (
            "Maya drove 150 miles at 50 miles per hour, took a 1-hour rest break, then drove "
            "60 miles at 30 miles per hour. How many hours did the whole journey take?"
        ),
    },
    {
        "problem_id": "hard-020",
        "answer": "10",
        "domain": "coins",
        "problem_en": (
            "Rohan has dimes and quarters worth $4.50 in total. He has 20 dimes. "
            "How many quarters does he have?"
        ),
    },
    {
        "problem_id": "hard-021",
        "answer": "44",
        "domain": "geometry",
        "problem_en": (
            "A rectangular garden is 14 meters long and 6 meters wide. A 1-meter-wide path "
            "surrounds the garden on all sides. What is the area of the path in square meters?"
        ),
    },
    {
        "problem_id": "hard-022",
        "answer": "60",
        "domain": "inventory",
        "problem_en": (
            "Box A contains 15 pens and Box B contains three times as many pens as Box A. "
            "When the two boxes are combined, how many pens are there in total?"
        ),
    },
    {
        "problem_id": "hard-023",
        "answer": "5",
        "domain": "shopping",
        "problem_en": (
            "Renting one video costs $12 and each additional video costs $4. "
            "Kavita paid $32 in total. How many additional videos did she rent?"
        ),
    },
    {
        "problem_id": "hard-024",
        "answer": "12",
        "domain": "work_rate",
        "problem_en": (
            "A tank holds 480 liters of water. A pipe fills it at 60 liters per hour while a leak "
            "drains 20 liters per hour. If the tank starts empty, how many hours will it take to fill?"
        ),
    },
    {
        "problem_id": "hard-025",
        "answer": "60",
        "domain": "business",
        "problem_en": (
            "The baking club baked 30 cupcakes and sold them for $3 each. They sold two-thirds "
            "of all the cupcakes. How many dollars did they earn from the sale?"
        ),
    },
    {
        "problem_id": "hard-026",
        "answer": "20",
        "domain": "fuel",
        "problem_en": (
            "A car uses 8 liters of fuel for every 100 kilometers. How many liters of fuel will "
            "it use for a 250-kilometer trip?"
        ),
    },
    {
        "problem_id": "hard-027",
        "answer": "42",
        "domain": "age",
        "problem_en": (
            "A father is three times as old as his son. The difference between their ages is 28 years. "
            "How old is the father?"
        ),
    },
    {
        "problem_id": "hard-028",
        "answer": "13",
        "domain": "sequence",
        "problem_en": (
            "In a store, the first item costs $1 and each following item costs three times as much "
            "as the previous one. What is the total cost of three items?"
        ),
    },
    {
        "problem_id": "hard-029",
        "answer": "500",
        "domain": "attendance",
        "problem_en": (
            "Over three performances a theater hosted 900 people in total. The first two performances "
            "had the same attendance and the third had 300 more than each of the first two. "
            "How many people attended the third performance?"
        ),
    },
    {
        "problem_id": "hard-030",
        "answer": "750",
        "domain": "salary",
        "problem_en": (
            "Meera earns $2000 each month. She pays 25% of it in tax and then spends half of what "
            "remains on rent. How many dollars does she have left after paying rent?"
        ),
    },
]


def verify(problem: dict[str, str]) -> None:
    """Independent arithmetic re-derivation; raise on mismatch."""
    pid = problem["problem_id"]
    checks = {
        "hard-001": lambda: 4 * 2 + 3 * 5 - 2,
        "hard-002": lambda: (60 * 2 + 90 * 1) / 3,
        "hard-003": lambda: (2 * 4 + 3 * 3) * 2,
        "hard-004": lambda: 1 / (1 / 6 + 1 / 3),
        "hard-005": lambda: (60 - 12) / 3 * 2,
        "hard-006": lambda: 20 * (1 + 2 + 4 + 8),
        "hard-007": lambda: (56 / 2 - 8) / 2,
        "hard-008": lambda: 40 / (1 - 1 / 2 - 1 / 3),
        "hard-009": lambda: 108 / 3 + 2,
        "hard-010": lambda: 80 * 0.75 * 0.8,
        "hard-011": lambda: 30 * (100 / (20 + 30)),
        "hard-012": lambda: 120 * (2 / 3) * (1 / 2),
        "hard-013": lambda: (100 - 5 * 12) / 8,
        "hard-014": lambda: 4 * 25 - (20 + 30 + 15),
        "hard-015": lambda: 100 / (12 + 8),
        "hard-016": lambda: 60 * 1.25,
        "hard-017": lambda: 5 * 4 * (1 / 2),
        "hard-018": lambda: 200 * (2 / 5) + 50,
        "hard-019": lambda: 150 / 50 + 1 + 60 / 30,
        "hard-020": lambda: (450 - 20 * 10) / 25,
        "hard-021": lambda: (14 + 2) * (6 + 2) - 14 * 6,
        "hard-022": lambda: 15 * 4,
        "hard-023": lambda: (32 - 12) / 4,
        "hard-024": lambda: 480 / (60 - 20),
        "hard-025": lambda: 30 * (2 / 3) * 3,
        "hard-026": lambda: 8 / 100 * 250,
        "hard-027": lambda: 28 / 2 * 3,
        "hard-028": lambda: 1 + 3 + 9,
        "hard-029": lambda: (900 - 300) / 3 + 300,
        "hard-030": lambda: 2000 * 0.75 * 0.5,
    }
    expected = checks[pid]()
    if abs(expected - int(problem["answer"])) > 1e-9:
        raise ValueError(f"{pid}: derived {expected} != declared {problem['answer']}")


HINDI: dict[str, str] = {
    "hard-001": "एक स्टेशनरी की दुकान में पेन की कीमत $2 प्रत्येक और नोटबुक की कीमत $5 प्रत्येक है। प्रिया ने 4 पेन और 3 नोटबुक खरीदीं और पूरी खरीदारी पर $2 का कूपन इस्तेमाल किया। उसने कुल मिलाकर कितने डॉलर चुकाए?",
    "hard-002": "एक ट्रेन 2 घंटे तक 60 मील प्रति घंटे की रफ्तार से चली, फिर अगले 1 घंटे तक 90 मील प्रति घंटे की रफ्तार से चली। पूरी यात्रा में उसकी औसत गति मील प्रति घंटे में क्या थी?",
    "hard-003": "एक फल विक्रेता ने $4 प्रति किलोग्राम पर 2 किलोग्राम सेब और $3 प्रति किलोग्राम पर 3 किलोग्राम संतरे खरीदे। उसने सब कुछ अपनी खरीद की कीमत के 200% पर बेच दिया। उसे कितने डॉलर मिले?",
    "hard-004": "नली A एक टैंक को 6 घंटे में भरती है और नली B उसी टैंक को 3 घंटे में भरती है। यदि दोनों नलियाँ एक साथ खोल दी जाएँ, तो टैंक को भरने में कितने घंटे लगेंगे?",
    "hard-005": "सारा रवि से दोगुनी उम्र की है। छह साल बाद, उनकी उम्रों का योग 60 होगा। अभी सारा की उम्र कितनी है?",
    "hard-006": "नेहा ने पहले दिन 20 पृष्ठ पढ़े और अगले तीन दिनों में हर अगले दिन पढ़े गए पृष्ठों की संख्या को दोगुना करती गई। चार दिनों में उसने कुल मिलाकर कितने पृष्ठ पढ़े?",
    "hard-007": "एक आयत की लंबाई उसकी चौड़ाई से 8 सेंटीमीटर अधिक है, और उसका परिमाप 56 सेंटीमीटर है। आयत की चौड़ाई कितने सेंटीमीटर है?",
    "hard-008": "तीन दोस्तों ने मिलकर एक उपहार खरीदा। पूजा ने कीमत का आधा हिस्सा, अंजलि ने एक-तिहाई हिस्सा, और रीना ने बचे हुए $40 का भुगतान किया। उपहार की कीमत कितने डॉलर थी?",
    "hard-009": "तीन क्रमागत सम संख्याओं का योग 108 है। तीनों में से सबसे बड़ी संख्या कौन सी है?",
    "hard-010": "एक जैकेट की कीमत $80 है। दुकान उस पर पहले 25% की छूट देती है, फिर घटाई गई कीमत पर अतिरिक्त 20% की छूट देती है। अंतिम कीमत कितने डॉलर है?",
    "hard-011": "अमित और बेन 100 मील दूर से शुरू करके एक-दूसरे की ओर चलते हैं, अमित 20 मील प्रति घंटे और बेन 30 मील प्रति घंटे की रफ्तार से। जब वे मिलेंगे तब बेन कितने मील चल चुका होगा?",
    "hard-012": "एक फल विक्रेता के पास शुरू में 120 सेब थे। उसने सुबह उनका एक-तिहाई बेच दिया, फिर बचे हुए सेबों का आधा दोपहर में बेच दिया। अंत में कितने सेब बचे?",
    "hard-013": "रिया ने एक शो के लिए $12 प्रत्येक के हिसाब से 5 वयस्क टिकट खरीदे और कुछ बच्चों के टिकट $8 प्रत्येक पर खरीदे। उसने कुल $100 का भुगतान किया। उसने कितने बच्चों के टिकट खरीदे?",
    "hard-014": "चार संख्याओं का औसत 25 है। तीन संख्याएँ 20, 30 और 15 हैं। चौथी संख्या क्या है?",
    "hard-015": "मशीन A प्रति घंटे 12 खिलौने बनाती है और मशीन B प्रति घंटे 8 खिलौने बनाती है। साथ काम करते हुए उन्हें 100 खिलौने बनाने में कितने घंटे लगेंगे?",
    "hard-016": "करण ने एक बैग $60 में खरीदा और उसे 25% लाभ पर बेच दिया। उसने बैग कितने डॉलर में बेचा?",
    "hard-017": "एक 5-मीटर लंबी रस्सी को प्रति मीटर 4 बराबर टुकड़ों में काटा गया। बाद में सभी टुकड़ों में से आधे टुकड़े फेंक दिए गए। कितने टुकड़े रखे गए?",
    "hard-018": "एक दुकान में 200 नोटबुक थीं। उसने उनमें से तीन-पाँचवाँ हिस्सा बेच दिया और फिर 50 और नोटबुकों की आपूर्ति मिली। अब दुकान में कितनी नोटबुक हैं?",
    "hard-019": "माया ने 50 मील प्रति घंटे की रफ्तार से 150 मील की दूरी तय की, 1 घंटे का ब्रेक लिया, फिर 30 मील प्रति घंटे की रफ्तार से 60 मील की दूरी तय की। पूरी यात्रा में कुल कितने घंटे लगे?",
    "hard-020": "रोहन के पास कुल $4.50 मूल्य के सिक्के हैं जिनमें डाइम और क्वार्टर शामिल हैं। उसके पास 20 डाइम हैं। उसके पास कितने क्वार्टर हैं?",
    "hard-021": "एक आयताकार बगीचा 14 मीटर लंबा और 6 मीटर चौड़ा है। बगीचे के चारों ओर 1-मीटर चौड़ा रास्ता बना है। रास्ते का क्षेत्रफल वर्ग मीटर में कितना है?",
    "hard-022": "डिब्बे A में 15 पेन हैं और डिब्बे B में डिब्बे A से तीन गुने पेन हैं। दोनों डिब्बों को मिला देने पर कुल कितने पेन होंगे?",
    "hard-023": "एक वीडियो किराए पर लेने की कीमत $12 है और हर अतिरिक्त वीडियो की कीमत $4 है। कविता ने कुल $32 का भुगतान किया। उसने कितने अतिरिक्त वीडियो किराए पर लिए?",
    "hard-024": "एक टैंक में 480 लीटर पानी आ सकता है। एक पाइप उसे 60 लीटर प्रति घंटे की दर से भरता है, जबकि एक रिसाव 20 लीटर प्रति घंटे की दर से पानी निकालता है। यदि टैंक शुरू में खाली है, तो उसे भरने में कितने घंटे लगेंगे?",
    "hard-025": "बेकिंग क्लब ने 30 कपकेक बनाए और उन्हें $3 प्रत्येक पर बेचा। उन्होंने सभी कपकेकों का दो-तिहाई हिस्सा बेचा। उन्होंने बिक्री से कितने डॉलर कमाए?",
    "hard-026": "एक कार हर 100 किलोमीटर के लिए 8 लीटर ईंधन इस्तेमाल करती है। 250 किलोमीटर की यात्रा के लिए उसे कितने लीटर ईंधन लगेगा?",
    "hard-027": "एक पिता अपने बेटे से तीन गुना बड़ा है। उनकी उम्रों का अंतर 28 वर्ष है। पिता की उम्र कितनी है?",
    "hard-028": "एक दुकान में पहली वस्तु की कीमत $1 है और हर अगली वस्तु की कीमत पिछली वस्तु से तीन गुनी है। तीन वस्तुओं की कुल कीमत कितनी है?",
    "hard-029": "तीन शो में मिलाकर एक थिएटर में कुल 900 लोग आए। पहले दो शो में समान संख्या में लोग आए और तीसरे शो में पहले दो में से प्रत्येक से 300 अधिक लोग आए। तीसरे शो में कितने लोग आए?",
    "hard-030": "मीरा हर महीने $2000 कमाती है। वह उसमें से 25% कर में चुकाती है और फिर बची हुई राशि का आधा किराए पर खर्च करती है। किराया चुकाने के बाद उसके पास कितने डॉलर बचते हैं?",
}


def main() -> None:
    output = Path("data/processed/hard_problems.jsonl")
    audit = Path("data/annotations/hard_translation_audit.csv")
    for problem in PROBLEMS:
        verify(problem)
        problem = dict(problem)
        problem["problem_hi"] = HINDI[problem["problem_id"]]
        problem["answer_type"] = "numeric"
        problem["difficulty"] = "hard"
        problem["source"] = "authored_hard_v1"
        problem["split"] = "hard"
        problem["translation_reviewed"] = False
        problem["translation_audit_status"] = "pending"
        with output.open("a", encoding="utf-8") as handle:
            import json
            handle.write(json.dumps(problem, ensure_ascii=False) + "\n")
    with audit.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["answer", "problem_en", "problem_hi", "problem_id", "review_status", "reviewer_notes"])
        for problem in PROBLEMS:
            writer.writerow(
                [problem["answer"], problem["problem_en"], HINDI[problem["problem_id"]], problem["problem_id"], "", ""]
            )
    print(f"wrote {len(PROBLEMS)} verified problems to {output}")
    print(f"wrote review sheet to {audit}")


if __name__ == "__main__":
    main()