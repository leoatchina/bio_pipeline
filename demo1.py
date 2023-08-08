#!/usr/bin/env python3
import os
import argparse
from pipeline import Pipeline

parser = argparse.ArgumentParser(description = "ngs demo pipeline")
parser.add_argument('-t', type = int, help = "run mode OR not run, 1 for true, 0 for false", default = 1, dest = 'run')
args = parser.parse_args()
os.system("mkdir -p demo/output")
demo_record = "demo/output/demo.csv"


# create pipeline
pipeline = Pipeline(demo_record)

fq1 = "demo/input/SRR1770413_1.head.fastq.gz"
fq2 = "demo/input/SRR1770413_2.head.fastq.gz"

ID = os.path.basename(fq1).split("_")[0]

bwa_mem_template = "bwa mem -t 2 -R '@RG\\tID:test\\tPL:illumina\\tSM:E.coli_K12' demo/genome/E.coli_K12_MG1655.fa {} {} | samtools view -Sb - > demo/output/{}.bwa_mem.bam"
bwa_mem_cmd = bwa_mem_template.format(fq1, fq2, ID)
pipeline.append(ID, "bwa_mem", bwa_mem_cmd, log = "demo/output/bwa_mem.log")

reorder_template = "samtools sort -@ 2 -m 1G -O bam \
  -o demo/output/{}.reorder.bwa_mem.bam \
  demo/output/{}.bwa_mem.bam"
reorder_cmd = reorder_template.format(ID, ID)
pipeline.append(ID, "reorder", reorder_cmd, log = "demo/output/reorder.log")

mark_dup_template = "java -Xmx4g -Djava.io.tmpdir=/tmp \
    -jar demo/tools/picard-tools-1.119/MarkDuplicates.jar \
    I=demo/output/{}.reorder.bwa_mem.bam \
    O=demo/output/{}.nodup.reorder.bwa_mem.bam \
    METRICS_FILE=demo/output/duplicate_report.txt \
    CREATE_INDEX=true \
    ASSUME_SORTED=true \
    REMOVE_DUPLICATES=true \
    VALIDATION_STRINGENCY=LENIENT"
mark_dup_cmd = mark_dup_template.format(ID, ID)
pipeline.append(ID, "mark_dup", mark_dup_cmd, log = "demo/output/mark_dup.log")

print_reads_template = "java -Xmx4g -Djava.io.tmpdir=/tmp \
    -jar demo/tools/GATK/GenomeAnalysisTK-3.8-0.jar \
    -T PrintReads \
    -R demo/genome/E.coli_K12_MG1655.fa \
    -I demo/output/{}.nodup.reorder.bwa_mem.bam \
    -o demo/output/{}.recal.bam \
    -l INFO \
    --read_filter MappingQualityZero"
print_reads_cmd = print_reads_template.format(ID, ID, ID)
pipeline.append(ID, "print_reads", print_reads_cmd, log = "demo/output/print_reads.log")

gatk_vcf_template = "java -Xmx4g -Djava.io.tmpdir=/tmp \
    -jar demo/tools/GATK/GenomeAnalysisTK-3.8-0.jar \
    -T HaplotypeCaller \
    -R demo/genome/E.coli_K12_MG1655.fa \
    -nct 2 \
    -I demo/output/{}.recal.bam \
    -o demo/output/{}.gatk.vcf"
gatk_vcf_cmd = gatk_vcf_template.format(ID, ID)
pipeline.append(ID, "gatk_vcf", gatk_vcf_cmd, log = "demo/output/gatk_vcf.log")

pipeline.run_pipeline(args.run)
