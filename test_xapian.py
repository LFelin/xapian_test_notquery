"""Reproduce a Xapian 2.x bug: a person excluded with AND_NOT is returned.

Usage:

    python3 test_xapian.py [NB_DOCS]

The database holds NB_DOCS persons (default 46342):

    - every person is a man (term sex:male), except person 2;
    - person 2 is a woman (term sex:female), born 19850312;
    - person 3 is a man, deleted (term deleted), born 20100615.

The query is "men not deleted OR women not deleted, born in 2010":

    ((sex:male AND NOT deleted) OR (sex:female AND NOT deleted))
        AND birthdate BETWEEN 20100101 AND 20101231

The only person born in 2010 is deleted: the expected result is nobody.
Xapian 2.0.0 and 2.1.0 return person 3. Xapian 1.4.30 returns nobody.

Exit code: 1 if the bug is present, 0 otherwise.
"""
import sys

import xapian
from xapian import Query

BIRTHDATE = 0


def build_database(nb_docs):
    db = xapian.WritableDatabase('', xapian.DB_BACKEND_INMEMORY)
    for docid in range(1, nb_docs + 1):
        doc = xapian.Document()
        if docid == 2:
            doc.add_term('sex:female')
            doc.add_value(BIRTHDATE, '19850312')
        elif docid == 3:
            doc.add_term('sex:male')
            doc.add_term('deleted')
            doc.add_value(BIRTHDATE, '20100615')
        else:
            doc.add_term('sex:male')
        db.replace_document(docid, doc)
    db.commit()
    return db


NOT_DELETED = Query(Query.OP_AND_NOT, Query.MatchAll, Query('deleted'))
BORN_IN_2010 = Query(Query.OP_VALUE_RANGE, BIRTHDATE, '20100101', '20101231')

# "AND NOT deleted" in each branch of the OR: wrong result
BUGGY = Query(Query.OP_AND, [
    Query(Query.OP_OR, [Query(Query.OP_AND, [Query('sex:male'), NOT_DELETED]),
                        Query(Query.OP_AND, [Query('sex:female'), NOT_DELETED])]),
    BORN_IN_2010])

# (sex:male OR sex:female) AND NOT deleted AND born in 2010: right result
FACTORIZED = Query(Query.OP_AND, [
    Query(Query.OP_OR, [Query('sex:male'), Query('sex:female')]),
    NOT_DELETED,
    BORN_IN_2010])


def describe(db, docid):
    doc = db.get_document(docid)
    terms = ', '.join(t.term.decode() for t in doc.termlist())
    return f'person {docid}: {terms}, born {doc.get_value(BIRTHDATE).decode()}'


def search(db, query, weight):
    enquire = xapian.Enquire(db)
    enquire.set_query(query)
    enquire.set_weighting_scheme(weight)
    docids = sorted(m.docid for m in enquire.get_mset(0, db.get_doccount()))
    return [describe(db, docid) for docid in docids]


def main():
    nb_docs = int(sys.argv[1]) if len(sys.argv) > 1 else 46342
    db = build_database(nb_docs)
    print(f'Xapian {xapian.version_string()}, {nb_docs} persons')
    print('Query: men not deleted OR women not deleted, born in 2010')
    print('Expected: nobody')
    print()

    bug = False
    for qname, query in (('AND NOT in each branch', BUGGY),
                         ('AND NOT factorized', FACTORIZED)):
        for wname, weight in (('BM25Weight', xapian.BM25Weight()),
                              ('BoolWeight', xapian.BoolWeight())):
            got = search(db, query, weight)
            wrong = bool(got)
            bug = bug or wrong
            print(f'{qname:22} {wname:10} Got: {"[" + "; ".join(got) + "]" if got else "nobody"}'
                  f'{"  -> WRONG" if wrong else ""}')

    print()
    if bug:
        print(f'BUG: Xapian {xapian.version_string()} returns a deleted person')
        return 1
    print(f'OK: Xapian {xapian.version_string()} returns nobody')
    return 0


if __name__ == '__main__':
    sys.exit(main())
