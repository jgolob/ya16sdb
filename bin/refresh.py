#!/usr/bin/env python3
"""
Append new records with old records

Sequences that have no_features or passed all filtering into the
annotations_out are appended to the versions_out file.

Sequences that did not pass the vsearch or tax_id update_taxids steps will be
not included in the versions_out file and consequently will be re-downloaded

Sequence ids in the fasta file are compared with the seq_annos. If any seq.id
or seqname not present in either source all records by accession associated
will be dropped and re-downloaded at a later time.
"""

import argparse
import itertools
import pandas

from Bio import SeqIO


def main():
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)

    p.add_argument(
        'ncbi',
        help='list of all the latest ncbi versions')

    p.add_argument(
        'new_fasta',
        help='records file in fasta format')
    p.add_argument(
        'previous_fasta',
        help='records file in fasta format')

    p.add_argument(
        'new_annos',
        help='records file in csv format')
    p.add_argument(
        'previous_annotations',
        help='records file in csv format')

    p.add_argument(
        'new_pubmed_annos',
        help='pubmed_annos file')
    p.add_argument(
        'previous_pubmed_annos',
        help='pubmed_annos file')

    p.add_argument(
        'new_references',
        help='references file')
    p.add_argument(
        'previous_references',
        help='references file')

    p.add_argument(
        'new_refseq_info',
        help='new refseq file')
    p.add_argument(
        'previous_refseq_info',
        help='previous refseq file')

    p.add_argument(
        'no_features',
        type=argparse.FileType('r'),
        help='list of versions downloaded with no 16s regions')
    p.add_argument(
        'previous_versions',
        type=argparse.FileType('r'),
        help='list of previously downloaded record versions')

    p.add_argument(
        'fasta_out',
        type=argparse.FileType('w'),
        help='records file in same Bio.SeqIO format as input')
    p.add_argument(
        'annotations_out',
        help='annotations output')
    p.add_argument(
        'pubmed_annos_out',
        help='pubmed_ids output')
    p.add_argument(
        'references_out',
        help='references output')
    p.add_argument(
        'refseq_info_out',
        help='refseqs output')
    p.add_argument(
        'versions_out',
        type=argparse.FileType('w'),
        help='list of all version downloaded')

    args = p.parse_args()

    new_annos = pandas.read_csv(args.new_annos, dtype=str)
    new_seqs = (s.id for s in SeqIO.parse(args.new_fasta, 'fasta'))

    # sync with fasta
    new_annos = new_annos[new_annos['seqname'].isin(new_seqs)]

    # read in prev_annos ignoring any accessions in the new data set
    prev_annos = pandas.read_csv(args.previous_annotations, dtype=str)

    # remove previous annos in new annos with same accessions
    prev_annos = prev_annos[
        ~prev_annos['accession'].isin(new_annos['accession'])]

    # combine annos files and retain column order
    columns = prev_annos.columns.tolist()
    for c in new_annos.columns:
        if c not in columns:
            columns.append(c)
    annos = prev_annos.append(new_annos)[columns]

    # remove anything dropped in ncbi
    ncbi = set(v.strip() for v in open(args.ncbi))
    annos = annos[annos['version'].isin(ncbi)]

    # read refseqs and append to old refseq list
    new_refseq_info = pandas.read_csv(args.new_refseq_info, dtype=str)
    prev_refseqs = pandas.read_csv(args.previous_refseq_info, dtype=str)
    prev_refseqs = prev_refseqs[
        ~prev_refseqs['version'].isin(new_refseq_info['version'])]
    refseqs = new_refseq_info.append(prev_refseqs)

    refseqs.to_csv(args.refseq_info_out, index=False)

    # remove annotations with refseq duplicates
    annos = annos[~annos['accession'].isin(refseqs['accession'])]

    assert(annos['seqname'] == annos['seqname'].drop_duplicates())

    """
    deduplicate and write fasta
    """
    written = set()
    new_fa = SeqIO.parse(args.new_fasta, 'fasta')
    prev_fa = SeqIO.parse(args.previous_fasta, 'fasta')
    for r in itertools.chain(new_fa, prev_fa):
        if r.id in annos['seqname'].values and r.id not in written:
            written.add(r.id)
            SeqIO.write(r, args.fasta_out, 'fasta')

    # write annotations
    annos.to_csv(args.annotations_out, index=False, date_format='%d-%b-%Y')

    '''
    just like with the seq_annos, replace old pubmed_ids with newly
    downloaded pubmed_ids, by accession
    '''
    new_pubmed = pandas.read_csv(args.new_pubmed_annos, dtype=str)
    prev_pubmed = pandas.read_csv(args.previous_pubmed_annos, dtype=str)
    prev_pubmed = prev_pubmed[~prev_pubmed.isin(prev_pubmed['accession'])]
    pubmed_ids = prev_pubmed.append(new_pubmed).drop_duplicates()
    pubmed_ids.to_csv(args.pubmed_annos_out, index=False)

    '''
    append new references. Use latest pubmed_ids and
    only if present in pubmed_ids dataframe
    '''
    new_refs = pandas.read_csv(args.new_references, dtype=str)
    prev_refs = pandas.read_csv(args.previous_references, dtype=str)
    prev_refs = prev_refs[~prev_refs['pubmed_id'].isin(new_refs['pubmed_id'])]
    refs = prev_refs.append(new_refs)
    refs = refs[refs['pubmed_id'].isin(pubmed_ids['pubmed_id'])]
    refs = refs.drop_duplicates()
    refs.to_csv(args.references_out, index=False)

    '''
    Filter the previous_versions with only existing records in ncbi. That way
    if any previous records appear again in a future esearch
    we can re-download.
    '''
    previous_versions = set(v.strip() for v in args.previous_versions)
    previous_versions = set(v for v in previous_versions if v in ncbi)

    '''
    output downloaded versions we do not want to download again. This
    includes records with no features and records that passed filtering
    up to this point
    '''
    versions = set(annos['version'].tolist())
    versions |= set(n.strip() for n in args.no_features)
    versions |= previous_versions

    for v in sorted(versions):
        args.versions_out.write(v + '\n')


if __name__ == '__main__':
    main()
