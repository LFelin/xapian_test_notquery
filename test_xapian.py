"""Reproduce a Xapian 2.x bug: AND_NOT inside OR returns an excluded document.

Usage:

    python3 test_xapian.py [NB_DOCS]

The script builds an in-memory database of NB_DOCS documents (default 46342):

    - every document has the term E, except docid 2;
    - docid 2 has the term D and the value 'a' in slot 0 (out of range);
    - docid 3 has the terms E and S and the value 'm' in slot 0 (in range).

and runs:

    ((E AND (ALL AND_NOT S)) OR (D AND (ALL AND_NOT S))) AND VALUE_RANGE(0, 'm', 'm')

The only document in the range (docid 3) has the term S, so the expected
result is empty. Xapian 2.0.0 and 2.1.0 return docid 3 with BM25Weight as soon
as tf(E) * NB_DOCS > 2^31 (NB_DOCS >= 46342 here). Xapian 1.4.30 returns
nothing.

Exit code: 1 if the bug is present, 0 otherwise.
"""
import sys

import xapian
from xapian import Query


def build_database(nb_docs):
    db = xapian.WritableDatabase('', xapian.DB_BACKEND_INMEMORY)
    for docid in range(1, nb_docs + 1):
        doc = xapian.Document()
        if docid == 2:
            doc.add_term('D')
            doc.add_value(0, 'a')
        elif docid == 3:
            doc.add_term('E')
            doc.add_term('S')
            doc.add_value(0, 'm')
        else:
            doc.add_term('E')
        db.replace_document(docid, doc)
    db.commit()
    return db


ALL_BUT_S = Query(Query.OP_AND_NOT, Query(''), Query('S'))
IN_RANGE = Query(Query.OP_VALUE_RANGE, 0, 'm', 'm')

# The AND_NOT is repeated in each branch of the OR: wrong result
BUGGY = Query(Query.OP_AND, [
    Query(Query.OP_OR, [Query(Query.OP_AND, [Query('E'), ALL_BUT_S]),
                        Query(Query.OP_AND, [Query('D'), ALL_BUT_S])]),
    IN_RANGE])

# Same query, with the AND_NOT moved out of the OR: right result
FACTORIZED = Query(Query.OP_AND, [
    Query(Query.OP_OR, [Query('E'), Query('D')]),
    ALL_BUT_S,
    IN_RANGE])

EXPECTED = []


def search(db, query, weight):
    enquire = xapian.Enquire(db)
    enquire.set_query(query)
    enquire.set_weighting_scheme(weight)
    return sorted(match.docid for match in enquire.get_mset(0, db.get_doccount()))


def main():
    nb_docs = int(sys.argv[1]) if len(sys.argv) > 1 else 46342
    print(f'Xapian {xapian.version_string()}')
    db = build_database(nb_docs)
    tf_e = db.get_termfreq('E')
    print(f'{nb_docs} documents, tf(E) = {tf_e}, '
          f'tf(E) * N = {tf_e * nb_docs} ({">" if tf_e * nb_docs > 2 ** 31 else "<="} 2^31)')
    print(f'Expected: {EXPECTED}')
    print()

    bug = False
    for qname, query in (('buggy', BUGGY), ('factorized', FACTORIZED)):
        print(f'{qname}: {query}')
        for wname, weight in (('BM25Weight', xapian.BM25Weight()),
                              ('BoolWeight', xapian.BoolWeight())):
            got = search(db, query, weight)
            status = 'OK' if got == EXPECTED else 'WRONG'
            print(f'    {wname:10}  got {got}  {status}')
            if got != EXPECTED:
                bug = True
                for docid in got:
                    doc = db.get_document(docid)
                    terms = [t.term.decode() for t in doc.termlist()]
                    print(f'        docid {docid}: terms {terms}, value {doc.get_value(0)!r}')
        print()

    if bug:
        print(f'> BUG: Xapian {xapian.version_string()} returns a document that has the term S')
        return 1
    print(f'> OK: Xapian {xapian.version_string()} returns the expected result')
    return 0


if __name__ == '__main__':
    sys.exit(main())
