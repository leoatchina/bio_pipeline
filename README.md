# 多进程运行生信分析流程的一个python类
## 示范
请见 **demo1.py**和**demo2.py**两个文件
其中demo1.py文件根据[GATK4.0和全基因组数据分析实践（上）](https://zhuanlan.zhihu.com/p/33891718)内容，
用了gatk3和picard,直接可以用
> python demo1.py -t0 运行
你可以在 `demo/output`文件夹下找到记录文件和结果
demo2.py为肿瘤样本外显子mutect2分析的部分代码，需要安装`bwa`, `samtools`等

## 场景
在[我的docker平台](https://github.com/leoatchina/leoatchina-datasci)上，
即是以这个类为基础，在网页端直接不用nohup启动分析流程，不需要时刻去往脚本里扔参数，会自动记录log，写入运行时间和步骤。

## 起因
怎么样使用服务器，高效地跑WES/WGS的pipeline，是每个生信人员工作中都会碰到的问题。
大家可能看到过很多用perl，shell跑pipeline的示范脚本。但是,一般来说示范脚本都是用一两个样本进行演示,而在实际工作中,
常碰到要处理几十上百样本的情况,本人碰到过的情况是300多例。
需要充分地使用cpu/memory出运算结果用于分析.对于多个样本,多进程并行同时运算是容易想到的方法
perl本人一直不是很喜欢，shell 脚本的功能较弱。
因此，我用python的multiprocessing里的Pool进程池技术实现了多个样本并行跑, 后来又加入了流程控制，过程记录，内存/CPU分配等功能。

## 思路
1. 对于一组数据构建一个`pipeline`，`pipleine`的一个环节为一个`procedure`, 如`bwa`，`samtools`,
   把所有的`procedure`在读入`fq.gz`文件时，都先`计划`好 ,然后依次执行。
2. 用了python里的`OrderedDict`作为这个`计划`的主体,以`procedure`为`key`,`value`为运算命令`cmd`, 计算结果`target`, 记录文件`log`等
3. 同时，用了一个`csv`文件作为记录下已跑流程结果和运算时间，在因为某些原因需要中断，重启后不需要从头再跑，直接运行原命令即可.
4. 为了调试运行，有一个参数`test`，默认为1，在此状态下只输出运行代码而不实际运行

## 使用
以`wes`为例,一个样本可能有`bwa_mem`・`samtools sort`,`markdup`,`merge`,`bqsr`,`applybqsr`,`haplotypecaller`等步骤
1. 用`记录文件`，`是否test`等初始化Pipeline类pipeline，并用本脚本里提供的函数获取系统`cpu`和`memory`
2. 遍历文件夹，读取需要进行`vcf call`的样本，获得`ID`,在脚本内形成相应的运行`cmd`, 和`target`, `log`, `run_sync`等一起**append**到pipeline里
3. 最终，run_pipeline
4. 请仔细观察两个demo文件学习

## TODO
1. 在代码运行过程中，能按`ctrl+c`结束所有命令。现在能在docker里可以用重启container的方式强制结束所有进程,
2. 解决好诸如要全部样本先算好，再统计所有样本的分布的`多对一`依赖问题,在demo2里，只能先把不需要的代码注释掉，等全部基因步骤跑完后再跑后续流程
3. 能像`WDL` `snakemake`一样， 模板化运行脚本，现在用纯python写代码量明显多于perl和shell
4. 利用消息队列，`中心化/分布式`运行
