#!/usr/bin/env python3

import os
import sys
import argparse
from pipeline import Pipeline, return_cmd, sys_core, sys_mem


parser = argparse.ArgumentParser(description = "wes_test")
parser.add_argument("-m", type = int, help = "The process number run at a same time", default = 5, dest = "multi")
parser.add_argument("-t", type = int, help = "If test, deault 1", default = 1, dest = "test")
parser.add_argument("-r", type = int, help = "If rm , default 0", default = 0, dest = "rm")
parser.add_argument("-p", type = float, help = "Percent", default = 0.75, dest = "percent")


params = parser.parse_args()

per_mem  = int(sys_mem*params.percent/params.multi) if int(sys_mem*params.percent/params.multi) >= 3 else 4
per_core = int(sys_core*params.percent/params.multi) if int(sys_core*params.percent/params.multi) >= 1 else 1

all_rawdata_path = "../Rawdata"
all_cleandata_path = "../Cleandata"
all_tmp_path = "../Tmpdata"
all_results_path = "../Results"
all_log_path = "../Log"
pipeline = Pipeline('../Record/record.csv', params.multi, params.test)


# qc check and trim_galore, use fastqc to detect the quality of files before/after trim_galore
# actually, since the qualiy of rawdata is good, trim and fq_after were not processed
def qc(ID, kind, rawdata_path, cleandata_path):
    # find raw_data_path for fq.gz files
    find_cmd = "find {} -type f | sort | grep fq.gz$".format(rawdata_path)
    rawdata_files = return_cmd(find_cmd)
    # fastqc before
    os.system('mkdir -p ../fastqc/{}/before'.format(ID + kind))
    for rawdata_file in rawdata_files:
        fastqc_template = "fastqc -o ../fastqc/{ID}/before -t {per_core} {rawdata_file}"
        fastqc_cmd = fastqc_template.format(ID = ID + kind, per_core = per_core, rawdata_file = rawdata_file)
        pipeline.append(ID + kind, "fastqc_before", fastqc_cmd, rawdata_file, run_sync = True)
    multiqc_cmd = "multiqc -n {ID} -o ../fastqc/before ../fastqc/{ID}/before/*.zip".format(ID = ID + kind)
    pipeline.append(ID + kind, "multiqc_before", multiqc_cmd, ID + kind + ".html")
    # trim_glare
    # paired files to trim_galore
    # rawdata_files_paired = zip(rawdata_files[::2], rawdata_files[1::2])
    # for (fq1, fq2) in rawdata_files_paired:
        # trim_galore_cmd = "trim_galore --length 50 --stringency 5 -q 25 -e 0.1 \
            # --paired --phred33 \
            # -o {cleandata_path} \
            # {fq1} {fq2}".format(cleandata_path = cleandata_path, fq1 = fq1, fq2 = fq2)
        # pipeline.append(ID + kind, "trim_galore", trim_galore_cmd, run_sync = True, log = os.path.join(all_log_path, "{}.log".format(fq1)))
    # fastqc after
    # os.system('mkdir -p ../fastqc/{}/after'.format(ID + kind))
    # find_cmd = "find {} -type f | sort | grep fq.gz$".format(cleandata_path)
    # cleandata_files = return_cmd(find_cmd)
    # for cleandata_file in cleandata_files:
        # fastqc_template = "fastqc -o ../fastqc/{ID}/after -t {per_core} {cleandata_file}"
        # fastqc_cmd = fastqc_template.format(ID = ID + kind, per_core = per_core, cleandata_file = cleandata_file)
        # pipeline.append(ID + kind, "fastqc_after", fastqc_cmd, cleandata_file, run_sync = True)


# recal
def recal(ID, kind, data_path, tmp_path, target_path, rm = 0):
    find_cmd = "find {} -type f | sort | grep fq.gz$".format(data_path)
    fq_files = return_cmd(find_cmd)
    merge_bams = []
    for (fq1, fq2) in zip(fq_files[0::2], fq_files[1::2]):
        bam_name = os.path.basename(fq1).split(".")[0].replace("_1", "")
        # bwa_mem
        # for memory limitation,  samtools sort may be interrupt
        RG = '@RG\\tID:%s\\tPL:illumina\\tSM:%s' % (ID + kind, ID + kind)
        bwa_mem_template = 'bwa mem -t {per_core} -M -R \"{RG}\" \
                            /mnt/bioinfo/bundle/hg38/Homo_sapiens_assembly38.fasta \
                            {fq1} {fq2} | samtools sort -@ 1 -m 4G -o {tmp_path}/{bam_name}.sort.bam -'
        bwa_mem_cmd = bwa_mem_template.format(per_core = per_core - 1, RG = RG, fq1 = fq1, fq2 = fq2, tmp_path = tmp_path, bam_name = bam_name)
        log = os.path.join(tmp_path, bam_name + ".bwa_mem.log")
        pipeline.append(ID + kind, "bwa_mem_sort", bwa_mem_cmd, "{}.sort.bam".format(bam_name), log = log, run_sync = True)
        # sort
        # sort_template = 'gatk --java-options "-Xmx{per_mem}G -Djava.io.tmpdir=/tmp" SortSam \
                        # -SO coordinate \
                        # -I {tmp_path}/{bam_name}.bwa_mem.bam \
                        # -O {tmp_path}/{bam_name}.sort.bam'
        # sort_cmd = sort_template.format(tmp_path = tmp_path, bam_name = bam_name, per_mem = per_mem)
        # log = os.path.join(tmp_path, bam_name + ".sort.log")
        # pipeline.append(ID + kind, "sort", sort_cmd, "{}.sort.bam".format(bam_name), log = log, run_sync = True)
        # markdup
        mark_dup_template = 'gatk --java-options "-Xmx{per_mem}G -Djava.io.tmpdir=/tmp" \
                            MarkDuplicates \
                            -I {tmp_path}/{bam_name}.sort.bam \
                            -M {tmp_path}/{bam_name}.markdup.sort.metrics.txt \
                            -O {tmp_path}/{bam_name}.markdup.sort.bam'
        mark_dup_cmd = mark_dup_template.format(tmp_path = tmp_path, bam_name = bam_name, per_mem = per_mem)
        log = os.path.join(tmp_path, bam_name+".markdup.log")
        merge_bams.append("{tmp_path}/{bam_name}.markdup.sort.bam".format(tmp_path = tmp_path, bam_name = bam_name))
        pipeline.append(ID + kind, "markdup", mark_dup_cmd, "{}.markdup.sort.bam".format(bam_name), log = log, run_sync = True)
    # merge
    merge_bams_template = 'gatk --java-options "-Xmx{per_mem}G -Djava.io.tmpdir=/tmp" \
                            MergeSamFiles -O {tmp_path}/{ID}.merge.bam -I '
    merge_bams = " -I ".join(merge_bams)
    merge_bams_cmd = merge_bams_template.format(tmp_path = tmp_path, ID = ID + kind, per_mem = per_mem) + merge_bams
    log = os.path.join(tmp_path, ID + kind + ".merge.log")
    pipeline.append(ID + kind, "merge_bams", merge_bams_cmd, ID + kind + ".merge.bam", log = log, run_sync = True)
    # fixinfo
    fix_info_template = 'gatk --java-options "-Xmx{per_mem}G -Djava.io.tmpdir=/tmp" \
                        FixMateInformation \
                        -I {tmp_path}/{ID}.merge.bam \
                        -O {tmp_path}/{ID}.fix.merge.bam \
                        -SO coordinate'
    fix_info_cmd = fix_info_template.format(tmp_path = tmp_path, ID = ID + kind, per_mem = per_mem)
    log = os.path.join(tmp_path, ID + kind + ".fix.log")
    pipeline.append(ID + kind, "fix_info", fix_info_cmd, ID + kind + ".fix.merge.bam", log = log, run_sync = True)
    # index
    index_cmd = "samtools index {}/{}.fix.merge.bam".format(tmp_path, ID + kind)
    pipeline.append(ID + kind, "index_fix", index_cmd, ID + kind + ".fix.merge.bam")
    # bqsr
    bqsr_template = 'gatk --java-options "-Xmx{per_mem}G -Djava.io.tmpdir=/tmp" \
                    BaseRecalibrator \
                    -R /mnt/bioinfo/bundle/hg38/Homo_sapiens_assembly38.fasta \
                    -I {tmp_path}/{ID}.fix.merge.bam  \
                    --known-sites /mnt/bioinfo/bundle/hg38/Mills_and_1000G_gold_standard.indels.hg38.vcf.gz \
                    --known-sites /mnt/bioinfo/bundle/hg38/1000G_phase1.snps.high_confidence.hg38.vcf.gz \
                    --known-sites /mnt/bioinfo/bundle/hg38/beta/Homo_sapiens_assembly38.known_indels.vcf.gz \
                    -O {tmp_path}/{ID}.bqsr.table'
    bqsr_cmd = bqsr_template.format(ID = ID + kind, per_mem = per_mem, tmp_path = tmp_path)
    log = os.path.join(tmp_path, ID + kind + ".bqsr.log")
    pipeline.append(ID + kind, "bqsr", bqsr_cmd, ID + kind + ".BQSR.table", log = log, run_sync = True)
    # ApplyBQSR, instead PrintRead
    apply_bqsr_template = 'gatk --java-options "-Xmx{per_mem}G -Djava.io.tmpdir=/tmp" \
                            ApplyBQSR \
                            -R /mnt/bioinfo/bundle/hg38/Homo_sapiens_assembly38.fasta \
                            --bqsr-recal-file {tmp_path}/{ID}.bqsr.table \
                            -I {tmp_path}/{ID}.fix.merge.bam \
                            -O {target_path}/{ID}.recal.bam'
    apply_bqsr_cmd = apply_bqsr_template.format(per_mem = per_mem, tmp_path = tmp_path, ID = ID + kind, target_path = target_path)
    log = os.path.join(tmp_path, ID + kind + ".recal.log")
    pipeline.append(ID + kind, "recal", apply_bqsr_cmd, ID + kind + ".recal.bam", log = log, run_sync = True)
    # rm tmp_data_path, add -r1 when run this script
    if rm:
        pipeline.append(ID + kind, "rm_tmpdata", "rm -rf {}".format(tmp_path))
    # qualimap
    qualimap_template = "qualimap bamqc --java-mem-size={per_mem}G -gff ./exon_probe.GRCh38.gene.150bp.bed -bam {target_path}/{ID}.recal.bam"
    qualimpap_cmd = qualimap_template.format(per_mem = per_mem, target_path = target_path, ID = ID + kind)
    log = os.path.join(target_path, ID + kind + ".qualimpa.log")
    pipeline.append(ID + kind, "qualimap", qualimpap_cmd, ID + kind + ".recal.bam", log = log, run_sync = True)
    # HaplotypeCaller exon
    haplotype_caller_exon_template = 'gatk --java-options "-Xmx{per_mem}G -Djava.io.tmpdir=/tmp" \
                            HaplotypeCaller \
                            -R /mnt/bioinfo/bundle/hg38/Homo_sapiens_assembly38.fasta \
                            --native-pair-hmm-threads {per_core} \
                            --dbsnp /mnt/bioinfo/bundle/hg38/dbsnp_146.hg38.vcf.gz \
                            -I {target_path}/{ID}.recal.bam \
                            -O {target_path}/{ID}.exon.g.vcf \
                            -ERC GVCF'
    haplotype_caller_exon_cmd = haplotype_caller_exon_template.format(target_path = target_path, ID = ID + kind, per_mem = per_mem, per_core = per_core)
    log = os.path.join(target_path, ID + kind + ".hc.exon.log")
    pipeline.append(ID + kind, "haplotype_caller_exon", haplotype_caller_exon_cmd, ID + kind + ".exon.g.vcf", log = log, run_sync = True)


def pon(IDnormal, normal_bam, pon_vcf):
    pon_cmd = 'gatk --java-options "-Xmx{per_mem}G -Djava.io.tmpdir=/tmp" \
                Mutect2 \
                -R /mnt/bioinfo/bundle/hg38/Homo_sapiens_assembly38.fasta \
                --disable-read-filter MateOnSameContigOrNoMappedMateReadFilter \
                --germline-resource /mnt/bioinfo/bundle/Mutect2/af-only-gnomad.hg38.vcf.gz \
                -I {normal_bam} \
                -tumor {IDnormal}\
                -O {pon_vcf}'.format(per_mem = per_mem, normal_bam = normal_bam, IDnormal = IDnormal, pon_vcf = pon_vcf)
    log = os.path.join(all_log_path, "{}.pon.log".format(ID))
    pipeline.append(IDnormal, "pon", pon_cmd, log = log)


def mutect2_vcf2maf(IDnormal, normal_bam, IDtumor, tumor_bam, mutect2_vcf, mutect2_maf):
    mutect2_cmd = 'gatk --java-options "-Xmx{per_mem}G -Djava.io.tmpdir=/tmp" \
                    Mutect2 \
                    -R /mnt/bioinfo/bundle/hg38/Homo_sapiens_assembly38.fasta \
                    --germline-resource /mnt/bioinfo/bundle/Mutect2/af-only-gnomad.hg38.vcf.gz \
                    -I {normal_bam} \
                    -normal {IDnormal} \
                    -I {tumor_bam} \
                    -tumor {IDtumor} \
                    -pon ../Results/all.pon.vcf.gz \
                    --disable-read-filter MateOnSameContigOrNoMappedMateReadFilter \
                    --af-of-alleles-not-in-resource 0.0000025 \
                    -O {mutect2_vcf}'.format(per_mem = per_mem,
                                     normal_bam = normal_bam,
                                     tumor_bam = tumor_bam,
                                     IDnormal = IDnormal,
                                     IDtumor  = IDtumor,
                                     mutect2_vcf = mutect2_vcf)
                    # -L ./exon_probe.GRCh38.gene.150bp.bed \
    log = os.path.join(all_log_path, "{}.{}.mutect2.log".format(IDnormal, IDtumor))
    # mutect shoud be run after all pons done
    pipeline.append(IDnormal + "-" + IDtumor, "mutect2_gnomad", mutect2_cmd, log = log)

    # --filter-vcf /mnt/bioinfo/ExAC/ExAC_nonTCGA.r0.3.1.sites.vep.vcf.gz \
    vcf2maf_cmd = "perl /jupyter/bioinfo/vcf2maf/vcf2maf.pl \
                    --input-vcf {mutect2_vcf} \
                    --output-maf {mutect2_maf}  \
                    --ref-fasta /mnt/bioinfo/bundle/hg38/Homo_sapiens_assembly38.fasta.gz \
                    --vep-path /jupyter/bioinfo/share/ensembl-vep-95.2-0 \
                    --ncbi-build GRCh38 \
                    --tumor-id {IDtumor}  \
                    --normal-id {IDnormal}".format(mutect2_vcf = mutect2_vcf, mutect2_maf = mutect2_maf, IDnormal = IDnormal, IDtumor = IDtumor)
    log = os.path.join(all_log_path, "{}.{}.maf.log".format(IDnormal, IDtumor))
    pipeline.append(IDnormal + "-" + IDtumor, "vcf2maf", vcf2maf_cmd, log = log)


# wesfunction
def wes(ID, normal_path, tumor_path, normal_clean_path, tumor_clean_path, normal_tmp_path, tumor_tmp_path, target_path, rm = params.rm):
    for each in (normal_clean_path, tumor_clean_path, normal_tmp_path, tumor_tmp_path, target_path):
        os.system("mkdir -p {}".format(each))
    qc(ID, "normal", normal_path, normal_clean_path)
    qc(ID, "tumor", tumor_path, tumor_clean_path)
    recal(ID, "normal", normal_path, normal_tmp_path, target_path, params.rm)
    recal(ID, "tumor", tumor_path, tumor_tmp_path, target_path, params.rm)
    pon(ID + "normal", os.path.join(target_path, "{}normal.recal.bam".format(ID)), os.path.join(target_path, "{}.pon.vcf.gz".format(ID)))


############################################################# main ########################################################################
# find fq.gz files, pair them using zip, then add to pipeline
find_rawdata_path_cmd = "find {all_rawdata_path} -maxdepth 1 -type d | sort ".format(all_rawdata_path = all_rawdata_path)
# find origin paths
paths = return_cmd(find_rawdata_path_cmd)[1:]
normal_tumor = zip(paths[0::2], paths[1::2])

# TODO: ctrl+c to stop all cmds which is run by os.popen
try:
    gvcfs = []
    pons  = []
    for (normal_path, tumor_path) in normal_tumor:
        normal_path_name  = os.path.basename(normal_path)
        tumor_path_name   = os.path.basename(tumor_path)
        ID                = normal_path_name[:-3]
        normal_clean_path = os.path.join(all_cleandata_path, normal_path_name)
        tumor_clean_path  = os.path.join(all_cleandata_path, tumor_path_name)
        normal_tmp_path   = os.path.join(all_tmp_path, normal_path_name)
        tumor_tmp_path    = os.path.join(all_tmp_path, tumor_path_name)
        target_path       = os.path.join(all_results_path, ID)
        wes(ID, normal_path, tumor_path, normal_clean_path, tumor_clean_path, normal_tmp_path, tumor_tmp_path, target_path, rm = params.rm)
        # mutect shoud be run after all pons done, and merge
        mutect2_vcf2maf(ID+"normal", os.path.join(target_path, "{}.recal.bam".format(ID + "normal")),
            ID+"tumor", os.path.join(target_path, "{}.recal.bam".format(ID + "tumor")),
            os.path.join(target_path, "{}.mutect2.vcf".format(ID)),
            os.path.join("../Results/mutect2", "{}.vep.maf".format(ID)))
        gvcfs.append(os.path.join(target_path, ID+'normal.exon.g.vcf'))
        pons.append(os.path.join(target_path, "{}.pon.vcf.gz".format(ID)))
    # merge pon
    pons = " -vcfs ".join(pons)
    create_pon_cmd = 'gatk --java-options "-Xmx{per_mem}G -Djava.io.tmpdir=/tmp" \
        CreateSomaticPanelOfNormals  \
        -vcfs {pons} \
        -O ../Results/all.pon.vcf.gz'.format(per_mem = per_mem, pons = pons)
    log = os.path.join(all_log_path, "all.pon.log")
    pipeline.append("all", "create_pon", create_pon_cmd, log = log)

    # only use intervals
    gvcfs = " -V ".join(gvcfs)
    chrs  = ['chr' + str(i) for i in range(1, 23)]
    chrs.append('chrY')
    chrs.append('chrX')
    merge_vcfs  = []
    merge_vcfs2 = []
    for chr in chrs:
        # GenomicsDBImport
        genomics_dbimport_cmd = 'gatk --java-options "-Xmx{per_mem}G -Djava.io.tmpdir=/tmp" \
            GenomicsDBImport \
            -R /mnt/bioinfo/bundle/hg38/Homo_sapiens_assembly38.fasta \
            --overwrite-existing-genomicsdb-workspace \
            --genomicsdb-workspace-path ../Results/all/db/{chr} \
            -L {chr} \
            -V {gvcfs}'.format(per_mem = per_mem, gvcfs = gvcfs, chr = chr)
        pipeline.append(chr, "dbimport", genomics_dbimport_cmd, 'db_{chr}'.format(chr = chr))
        # GenotypeGVCFs
        genotype_gvcfs_cmd = 'gatk --java-options "-Xmx{per_mem}G -Djava.io.tmpdir=/tmp" \
            GenotypeGVCFs \
            -R /mnt/bioinfo/bundle/hg38/Homo_sapiens_assembly38.fasta \
            -V gendb://../Results/all/db/{chr} \
            -O ../Results/all/all.{chr}.db.vcf'.format(per_mem = per_mem, chr = chr)
        pipeline.append(chr, "genotype_gvcfs", genotype_gvcfs_cmd, 'all.{}.db.vcf'.format(chr))
        merge_vcfs.append('../Results/all/all.{}.db.vcf'.format(chr))
        # CombineGVCFs
        combine_gvcfs_cmd = 'gatk --java-options "-Xmx{per_mem}G -Djava.io.tmpdir=/tmp" \
            CombineGVCFs \
            -R /mnt/bioinfo/bundle/hg38/Homo_sapiens_assembly38.fasta \
            -O ../Results/all/all.{chr}.g.vcf \
            -L {chr} \
            -V {gvcfs}'.format(per_mem = per_mem, gvcfs = gvcfs, chr = chr)
        pipeline.append(chr, "combine_gvcfs", combine_gvcfs_cmd, 'all.{chr}.g.vcf'.format(chr = chr))
        # GenotypeGVCFs
        genotype_gvcfs_cmd2 = 'gatk --java-options "-Xmx{per_mem}G -Djava.io.tmpdir=/tmp" \
            GenotypeGVCFs \
            -R /mnt/bioinfo/bundle/hg38/Homo_sapiens_assembly38.fasta \
            -V ../Results/all/all.{chr}.g.vcf \
            -O ../Results/all/all.{chr}.vcf'.format(per_mem = per_mem, chr = chr)
        pipeline.append(chr, "genotype_gvcfs2", genotype_gvcfs_cmd2, 'all.{}.vcf'.format(chr))
        merge_vcfs2.append('../Results/all/all.{}.vcf'.format(chr))
    merge_vcfs  = " -I ".join(merge_vcfs)
    merge_vcfs2 = " -I ".join(merge_vcfs2)
    merge_cmd = 'gatk --java-options "-Xmx{per_mem}G -Djava.io.tmpdir=/tmp" \
        MergeVcfs \
        -I {merge_vcfs} \
        -O ../Results/all/all.db.vcf'.format(per_mem = per_mem, merge_vcfs = merge_vcfs)
    log = os.path.join(all_log_path, "all.merge_vcfs.log")
    pipeline.append('all', 'merge_vcfs', merge_cmd, log = log)
    merge_cmd2 = 'gatk --java-options "-Xmx{per_mem}G -Djava.io.tmpdir=/tmp" \
        MergeVcfs \
        -I {merge_vcfs2} \
        -O ../Results/all/all.vcf'.format(per_mem = per_mem, merge_vcfs2 = merge_vcfs2)
    log = os.path.join(all_log_path, "all.merge_vcfs2.log")
    pipeline.append('all2', 'merge_vcfs2', merge_cmd2, log = log)
    # vqsr snp
    vqsr_snp_cmd = 'gatk --java-options "-Xmx{per_mem}G -Djava.io.tmpdir=/tmp" \
        VariantRecalibrator \
        -mode SNP \
        -R /mnt/bioinfo/bundle/hg38/Homo_sapiens_assembly38.fasta \
        -resource hapmap,known=false,training=true,truth=true,prior=15.0:/mnt/bioinfo/bundle/hg38/hapmap_3.3.hg38.vcf \
        -resource omini,known=false,training=true,truth=false,prior=12.0:/mnt/bioinfo/bundle/hg38/1000G_omni2.5.hg38.vcf \
        -resource 1000G,known=false,training=true,truth=false,prior=10.0:/mnt/bioinfo/bundle/hg38/1000G_phase1.snps.high_confidence.hg38.vcf \
        -resource dbsnp,known=true,training=false,truth=false,prior=2.00:/mnt/bioinfo/bundle/hg38/dbsnp_146.hg38.vcf \
        -an DP -an QD -an FS -an SOR -an ReadPosRankSum -an MQRankSum \
        -tranche 100.0 -tranche 99.9 -tranche 99.0 -tranche 95.0 -tranche 90.0 \
        --tranches-file ../Results/all/all.db.snps.tranches \
        -V ../Results/all/all.db.vcf \
        -O ../Results/all/all.db.snps.vqsr.recal'.format(per_mem = per_mem)
        # --rscript-file ../Results/all/all.db.snps.plot.R \
    pipeline.append('all', 'vqsr_snp', vqsr_snp_cmd)
    apply_vqsr_snp_cmd = 'gatk --java-options "-Xmx{per_mem}G -Djava.io.tmpdir=/tmp" \
        ApplyVQSR \
        -mode SNP \
        -R /mnt/bioinfo/bundle/hg38/Homo_sapiens_assembly38.fasta \
        --recal-file ../Results/all/all.db.snps.vqsr.recal \
        --tranches-file ../Results/all/all.db.snps.tranches \
        -V ../Results/all/all.db.vcf \
        -O ../Results/all/all.db.snps.vqsr.vcf'.format(per_mem = per_mem)
    pipeline.append('all', 'apply_vqsr_snp', apply_vqsr_snp_cmd)
    # vqsr indel
    vqsr_indel_cmd = 'gatk --java-options "-Xmx{per_mem}G -Djava.io.tmpdir=/tmp" \
        VariantRecalibrator \
        -mode INDEL \
        -R /mnt/bioinfo/bundle/hg38/Homo_sapiens_assembly38.fasta \
        -resource mills,known=true,training=true,truth=true,prior=12.0:/mnt/bioinfo/bundle/hg38/Mills_and_1000G_gold_standard.indels.hg38.vcf \
        -resource dbsnp,known=true,training=false,truth=false,prior=2.0:/mnt/bioinfo/bundle/hg38/dbsnp_146.hg38.vcf \
        -an DP -an QD -an FS -an SOR -an ReadPosRankSum -an MQRankSum \
        --max-gaussians 6 \
        --tranches-file ../Results/all/all.db.indels.tranches \
        -V ../Results/all/all.db.snps.vqsr.vcf \
        -O ../Results/all/all.db.indels.vqsr.recal'.format(per_mem = per_mem)
        # --rscript-file ../Results/all/all.db.indels.plot.R \
    pipeline.append('all', 'vqsr_indel', vqsr_indel_cmd)
    apply_vqsr_indel_cmd = 'gatk --java-options "-Xmx{per_mem}G -Djava.io.tmpdir=/tmp" \
        ApplyVQSR \
        -mode INDEL \
        -R /mnt/bioinfo/bundle/hg38/Homo_sapiens_assembly38.fasta \
        --recal-file ../Results/all/all.db.indels.vqsr.recal \
        --tranches-file ../Results/all/all.db.indels.tranches \
        -V ../Results/all/all.db.snps.vqsr.vcf \
        -O ../Results/all/all.db.vqsr.vcf'.format(per_mem = per_mem)
    pipeline.append('all', 'apply_vqsr_indel', apply_vqsr_indel_cmd)

except KeyboardInterrupt:
    print("Ctrl+C pressed ,exiting")
    pipeline.terminate()
    sys.exit(0)
pipeline.run_pipeline()
