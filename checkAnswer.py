import re

def checkAnswer(answerline: str, response: str) -> bool:
    def normalize(s):
        return re.sub(r'\s+', ' ', s.strip().lower())

    normalized_response = normalize(response)

    # Extract main answer and notes inside parentheses
    paren_match = re.search(r'\((.*?)\)', answerline)
    notes = ""
    if paren_match:
        notes = paren_match.group(1)
        main_answer = answerline[:paren_match.start()].strip()
    else:
        main_answer = answerline.strip()

    accepts = []
    do_not_accepts = []

    if notes:
        # Split by ACCEPT and DO NOT ACCEPT carefully
        # e.g., "ACCEPT: GENERA; DO NOT ACCEPT: SPECIES"
        accept_match = re.search(r'ACCEPT\s*:\s*(.*?)(?:;|$)', notes, flags=re.IGNORECASE)
        if accept_match:
            accepts = [a.strip() for a in accept_match.group(1).split(';')]

        dna_match = re.search(r'DO NOT ACCEPT\s*:\s*(.*?)(?:;|$)', notes, flags=re.IGNORECASE)
        if dna_match:
            do_not_accepts = [d.strip() for d in dna_match.group(1).split(';')]

    # Check DO NOT ACCEPT first
    for dna in do_not_accepts:
        if normalize(dna) == normalized_response:
            return False

    # Check main answer
    if normalize(main_answer) == normalized_response:
        return True

    # Check ACCEPTs
    for acc in accepts:
        if normalize(acc) == normalized_response:
            return True

    return False