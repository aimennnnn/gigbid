import spacy
import seqeval


def run(frame):
    """Pull names, dates and amounts out of contracts."""
    prepared = seqeval.prepare(frame)
    return spacy.fit_predict(prepared)
