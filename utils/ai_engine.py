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


def compare_question(previous_cycle, current_cycle, question_no):

    if not previous_cycle:
        return "No Previous Data"

    prev_answer = next(
        (a for a in previous_cycle["answers"]
         if str(a["questionNo"]) == str(question_no)), None)

    curr_answer = next(
        (a for a in current_cycle["answers"]
         if str(a["questionNo"]) == str(question_no)), None)

    if not prev_answer or not curr_answer:
        return "No Data"

    change = prev_answer["rating"] - curr_answer["rating"]

    return classify_change(change)