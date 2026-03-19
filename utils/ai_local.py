from collections import Counter

ISSUE_KEYWORDS = {
    "water": ["water", "tap"],
    "garbage": ["garbage", "waste"],
    "roads": ["road", "pothole"],
    "electricity": ["electricity", "power"]
}

def generate_local_analysis(responses_text_list):

    detected_issues = []

    for text in responses_text_list:
        text_lower = text.lower()

        for issue, keywords in ISSUE_KEYWORDS.items():
            if any(word in text_lower for word in keywords):
                detected_issues.append(issue)

    issue_counts = Counter(detected_issues)
    top_issues = issue_counts.most_common(3)

    if not top_issues:
        return "No major issues detected"

    result = "Top Issues:\n"

    for i, (issue, count) in enumerate(top_issues, start=1):
        result += f"{i}. {issue} ({count})\n"

    return result