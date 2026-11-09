// Reproduce a Xapian 2.x bug: a person excluded with AND_NOT is returned.
//
// Build and run:
//
//     g++ -O2 -o test_xapian test_xapian.cc $(xapian-config --cxxflags --libs)
//     ./test_xapian [NB_DOCS]
//
// Same database and queries as test_xapian.py: see the README.
// Exit code: 1 if the bug is present, 0 otherwise.

#include <xapian.h>

#include <cstdio>
#include <cstdlib>
#include <iostream>
#include <string>
#include <vector>

using namespace std;

static const Xapian::valueno BIRTHDATE = 0;

static Xapian::WritableDatabase build_database(Xapian::docid nb_docs)
{
    Xapian::WritableDatabase db(string(), Xapian::DB_BACKEND_INMEMORY);
    for (Xapian::docid docid = 1; docid <= nb_docs; ++docid) {
        Xapian::Document doc;
        if (docid == 2) {
            doc.add_term("sex:female");
            doc.add_value(BIRTHDATE, "19850312");
        } else if (docid == 3) {
            doc.add_term("sex:male");
            doc.add_term("deleted");
            doc.add_value(BIRTHDATE, "20100615");
        } else {
            doc.add_term("sex:male");
        }
        db.replace_document(docid, doc);
    }
    db.commit();
    return db;
}

static string describe(const Xapian::Database& db, Xapian::docid docid)
{
    Xapian::Document doc = db.get_document(docid);
    string s = "person " + to_string(docid) + ": ";
    for (Xapian::TermIterator t = doc.termlist_begin(); t != doc.termlist_end(); ++t)
        s += *t + ", ";
    return s + "born " + doc.get_value(BIRTHDATE);
}

static vector<string> search(const Xapian::Database& db,
                             const Xapian::Query& query,
                             const Xapian::Weight& weight)
{
    Xapian::Enquire enquire(db);
    enquire.set_query(query);
    enquire.set_weighting_scheme(weight);
    Xapian::MSet mset = enquire.get_mset(0, db.get_doccount());
    vector<string> got;
    for (Xapian::MSetIterator m = mset.begin(); m != mset.end(); ++m)
        got.push_back(describe(db, *m));
    return got;
}

int main(int argc, char** argv)
{
    Xapian::docid nb_docs = argc > 1 ? strtoul(argv[1], NULL, 10) : 46342;
    Xapian::WritableDatabase db = build_database(nb_docs);
    cout << "Xapian " << Xapian::version_string() << ", " << nb_docs << " persons" << endl;
    cout << "Query: men not deleted OR women not deleted, born in 2010" << endl;
    cout << "Expected: nobody" << endl << endl;

    using Q = Xapian::Query;
    Q not_deleted(Q::OP_AND_NOT, Q::MatchAll, Q("deleted"));
    Q born_in_2010(Q::OP_VALUE_RANGE, BIRTHDATE, "20100101", "20101231");

    // "AND NOT deleted" in each branch of the OR: wrong result
    Q buggy(Q::OP_AND,
        Q(Q::OP_OR,
            Q(Q::OP_AND, Q("sex:male"), not_deleted),
            Q(Q::OP_AND, Q("sex:female"), not_deleted)),
        born_in_2010);

    // (sex:male OR sex:female) AND NOT deleted AND born in 2010: right result
    vector<Q> parts = {Q(Q::OP_OR, Q("sex:male"), Q("sex:female")),
                       not_deleted, born_in_2010};
    Q factorized(Q::OP_AND, parts.begin(), parts.end());

    struct { const char* name; Q query; } queries[] = {
        {"AND NOT in each branch", buggy}, {"AND NOT factorized", factorized},
    };
    Xapian::BM25Weight bm25;
    Xapian::BoolWeight boolweight;
    struct { const char* name; const Xapian::Weight& weight; } weights[] = {
        {"BM25Weight", bm25}, {"BoolWeight", boolweight},
    };

    bool bug = false;
    for (auto& q : queries) {
        for (auto& w : weights) {
            vector<string> got = search(db, q.query, w.weight);
            string text = "nobody";
            if (!got.empty()) {
                bug = true;
                text = "[";
                for (size_t i = 0; i < got.size(); ++i)
                    text += (i ? "; " : "") + got[i];
                text += "]  -> WRONG";
            }
            printf("%-22s %-10s Got: %s\n", q.name, w.name, text.c_str());
        }
    }
    fflush(stdout);

    cout << endl;
    if (bug) {
        cout << "BUG: Xapian " << Xapian::version_string()
             << " returns a deleted person" << endl;
        return 1;
    }
    cout << "OK: Xapian " << Xapian::version_string() << " returns nobody" << endl;
    return 0;
}
