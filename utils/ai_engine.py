def classify_change(score_change):

    if score_change >= 2:
        return "Significant Improvement"

    if score_change == 1:
        return "Slight Improvement"

    if score_change == 0:
        return "No Change"

    if score_change == -1:
        return "Slight Decline"

    return "Significant Decline"


def analyze_trends(grouped):

    for pid, data in grouped.items():

        data["cycles"].sort(key=lambda x: x["timestamp"])

        for i in range(len(data["cycles"])):

            if i == 0:
                data["cycles"][i]["status"] = "No Previous Data"
                continue

            prev = data["cycles"][i-1]["answers"]
            curr = data["cycles"][i]["answers"]

            change = 0

            for p in prev:
                match = next(
                    (c for c in curr if c["questionNo"] == p["questionNo"]),
                    None
                )
                if match:
                    change += p["rating"] - match["rating"]

            # 🔥 extra info (good for demo)
            data["cycles"][i]["score_change"] = change
            data["cycles"][i]["status"] = classify_change(change)

    return grouped