// Reproduce a Xapian 2.x bug: AND_NOT inside OR returns an excluded document.
//
// Build and run:
//
//     g++ -O2 -o test_xapian test_xapian.cc $(xapian-config --cxxflags --libs)
//     ./test_xapian [NB_DOCS]
//
// Same database and queries as test_xapian.py: see the README.
// Exit code: 1 if the bug is present, 0 otherwise.

#include <xapian.h>

#include <cstdlib>
#include <iostream>
#include <string>
#include <vector>

using namespace std;

static Xapian::WritableDatabase build_database(Xapian::docid nb_docs)
{
    Xapian::WritableDatabase db(string(), Xapian::DB_BACKEND_INMEMORY);
    for (Xapian::docid docid = 1; docid <= nb_docs; ++docid) {
        Xapian::Document doc;
        if (docid == 2) {
            doc.add_term("D");
            doc.add_value(0, "a");
        } else if (docid == 3) {
            doc.add_term("E");
            doc.add_term("S");
            doc.add_value(0, "m");
        } else {
            doc.add_term("E");
        }
        db.replace_document(docid, doc);
    }
    db.commit();
    return db;
}

static vector<Xapian::docid> search(const Xapian::Database& db,
                                    const Xapian::Query& query,
                                    const Xapian::Weight& weight)
{
    Xapian::Enquire enquire(db);
    enquire.set_query(query);
    enquire.set_weighting_scheme(weight);
    Xapian::MSet mset = enquire.get_mset(0, db.get_doccount());
    vector<Xapian::docid> docids;
    for (Xapian::MSetIterator m = mset.begin(); m != mset.end(); ++m)
        docids.push_back(*m);
    return docids;
}

static string to_string(const vector<Xapian::docid>& docids)
{
    string s = "[";
    for (size_t i = 0; i < docids.size(); ++i) {
        if (i) s += ", ";
        s += std::to_string(docids[i]);
    }
    return s + "]";
}

int main(int argc, char** argv)
{
    Xapian::docid nb_docs = argc > 1 ? strtoul(argv[1], NULL, 10) : 46342;
    cout << "Xapian " << Xapian::version_string() << endl;
    Xapian::WritableDatabase db = build_database(nb_docs);
    unsigned long long tf_e = db.get_termfreq("E");
    unsigned long long product = tf_e * nb_docs;
    cout << nb_docs << " documents, tf(E) = " << tf_e
         << ", tf(E) * N = " << product
         << (product > (1ULL << 31) ? " (> 2^31)" : " (<= 2^31)") << endl;
    cout << "Expected: []" << endl << endl;

    Xapian::Query all_but_s(Xapian::Query::OP_AND_NOT,
                            Xapian::Query(string()), Xapian::Query("S"));
    Xapian::Query in_range(Xapian::Query::OP_VALUE_RANGE, 0, "m", "m");

    // The AND_NOT is repeated in each branch of the OR: wrong result
    Xapian::Query buggy(Xapian::Query::OP_AND,
        Xapian::Query(Xapian::Query::OP_OR,
            Xapian::Query(Xapian::Query::OP_AND, Xapian::Query("E"), all_but_s),
            Xapian::Query(Xapian::Query::OP_AND, Xapian::Query("D"), all_but_s)),
        in_range);

    // Same query, with the AND_NOT moved out of the OR: right result
    vector<Xapian::Query> factorized_parts = {
        Xapian::Query(Xapian::Query::OP_OR, Xapian::Query("E"), Xapian::Query("D")),
        all_but_s,
        in_range,
    };
    Xapian::Query factorized(Xapian::Query::OP_AND,
                             factorized_parts.begin(), factorized_parts.end());

    struct { const char* name; Xapian::Query query; } queries[] = {
        {"buggy", buggy}, {"factorized", factorized},
    };

    bool bug = false;
    for (auto& q : queries) {
        cout << q.name << ": " << q.query.get_description() << endl;
        Xapian::BM25Weight bm25;
        Xapian::BoolWeight boolweight;
        struct { const char* name; const Xapian::Weight& weight; } weights[] = {
            {"BM25Weight", bm25}, {"BoolWeight", boolweight},
        };
        for (auto& w : weights) {
            vector<Xapian::docid> got = search(db, q.query, w.weight);
            cout << "    " << w.name << "  got " << to_string(got) << "  "
                 << (got.empty() ? "OK" : "WRONG") << endl;
            if (!got.empty()) bug = true;
        }
        cout << endl;
    }

    if (bug) {
        cout << "> BUG: Xapian " << Xapian::version_string()
             << " returns a document that has the term S" << endl;
        return 1;
    }
    cout << "> OK: Xapian " << Xapian::version_string()
         << " returns the expected result" << endl;
    return 0;
}
