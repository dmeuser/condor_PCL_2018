import subprocess
import os
import shutil
import pickle
import fileinput
import urllib
import json
import collections

# define workspace, base directory and output directory (has to be changed for different user)
workPath="/afs/cern.ch/work/d/dmeuser/alignment/PCL/condor_PCL_2018/run_directories"
basePath="/afs/cern.ch/user/d/dmeuser/alignment/PCL/condor_PCL_2018"
outputPath="/eos/cms/store/caf/user/dmeuser/PCL/condor_PCL_2018/output"

# method to merge two dictionaries (mostly used when adding lowPU runs into nominal range)
def merge_two_dicts(x, y):
    z = x.copy()   # start with x's keys and values
    z.update(y)    # modifies z with y's keys and values & returns None
    return z

# method to retrieve file list for given run in the form of {lumiNo: "file1, file2"} (currently only defined for 2018BCD)
def getFileList_run(run):
    run=int(run)
    if run<317080 or run>325175:    # check which run era has to be used
        print "Dataset to run "+run+" not defined"
    elif run<=319311:
        output=subprocess.check_output(["dasgoclient -query='lumi,file dataset=/StreamExpress/Run2018B-TkAlMinBias-Express-v1/ALCARECO run={}'".format(run)], shell=True)
    elif run<=320393:
        output=subprocess.check_output(["dasgoclient -query='lumi,file dataset=/StreamExpress/Run2018C-TkAlMinBias-Express-v1/ALCARECO run={}'".format(run)], shell=True)
    elif run<=325175:
        output=subprocess.check_output(["dasgoclient -query='lumi,file dataset=/StreamExpress/Run2018D-TkAlMinBias-Express-v1/ALCARECO run={}'".format(run)], shell=True)
    fileDict={}
    for line in output.split("\n"):     #create dictionary to save filenames per lumi (each line corresponds to one file)
        if len(line.split("["))==2 :
            lumi = line.split("[")[1].split("]")[0].split(",")      # get list of lumiNo from das output
            fileName = line.split("[")[0]
            for i in range(len(lumi)):
                if int(lumi[i])<20: continue    # first 20 lumi section should not be used for study
                fileDict[int(lumi[i])]=fileName
    with open("./testDict.pkl","wb") as f:      # write dictionary to pkl               
        pickle.dump(fileDict, f, pickle.HIGHEST_PROTOCOL)
    return fileDict
    
# method to create the log folder, returns path to log folder
def createLogFolder(run,lumi,HG_bool):
    if HG_bool:
        dirname=basePath+"/logs/HG_run"+str(run)+"/lumi_"+str(lumi)
    else :
        dirname=basePath+"/logs_LG/run"+str(run)+"/lumi_"+str(lumi)
        
    if not os.path.exists(dirname):
        try:
            os.makedirs(dirname)
        except OSError as exc: # Guard against race condition
            if exc.errno != errno.EEXIST:
                raise
    return dirname

# method to create the run folder, returns path to run folder
def createRunFolder(run,lumi,HG_bool):
    if HG_bool:
        dirname=workPath+"/HG_run"+str(run)+"/lumi_"+str(lumi)
    else :
        dirname=workPath+"/run"+str(run)+"/lumi_"+str(lumi)
        
    if not os.path.exists(dirname):
        try:
            os.makedirs(dirname)
        except OSError as exc: # Guard against race condition
            if exc.errno != errno.EEXIST:
                raise
    return dirname

# method to clean output folder (useful in case job are failing)
def cleanOutputFolder(run,HG_bool,complete):
    if HG_bool:
        dirname=outputPath+"/HG_run"+str(run)
    else :
        dirname=outputPath+"/run"+str(run)
    if os.path.exists(dirname):
        if complete:
            shutil.rmtree(dirname)
        else:
            if os.path.exists(dirname+"/promptCalibConditions.db"):
                os.remove(dirname+"/promptCalibConditions.db")
            if os.path.exists(dirname+"/treeFile.root"):
                os.remove(dirname+"/treeFile.root")
            

# method which return file list for a given starting lumi and given lumis per job
def getFileList_job(fileDict,lumi,LumisPerJob):
    fileList=""
    for i in range(0,LumisPerJob):      # loop over number of lumis per job
        if lumi+i in fileDict.keys():   # current lumi given bei start lumi + loop lumi
            if fileDict[lumi+i] not in fileList:    # only add file if not already in list
                fileList+="'"+fileDict[lumi+i]+"',\n"
    return fileList
    
# method which write mille config starting from template and replacing file list and start/stop lumi
def writeMilleConfig(run,HG_bool,lumi,LumisPerJob,fileList,dirRun):
    if HG_bool:
        fileName="milleStep_ALCA_HG.py"
    else:
        fileName="milleStep_ALCA.py"
    
    f = open(basePath+"/templates/"+fileName,'r')
    filedata = f.read()
    f.close()

    newdata = filedata.replace("'file:milleStep_RECO.root'",fileList)       # set file list
    newdata = newdata.replace("run:startLumi-run:endLumi",str(run)+":"+str(lumi)+"-"+str(run)+":"+str(lumi+LumisPerJob-1))      # set start and stop lumi

    f = open(dirRun+"/"+fileName,'w')   # write config to run directory
    f.write(newdata)
    f.close()
    
# method to write condor submit script for mille job log folder(needs argument used for milleStep.sh)
def writeMilleSubmit(run,HG_bool,lumi,fileList,dirname):
    with open(dirname+"/submit_mille.sub","w") as f:
        f.write("""
Universe   = vanilla
Executable = milleStep.sh
Arguments  = {0} {1} {3}
Log        = {2}/log_mille.log
Output     = {2}/out_mille.out
Error      = {2}/error_mille.error
x509userproxy = $ENV(X509_USER_PROXY)
+JobFlavour = "microcentury"
+AccountingGroup = "group_u_CMS.CAF.ALCA"
Queue
""".format(run,HG_bool,dirname,lumi))
    return dirname+"/submit_mille.sub"

# method to write condor submit script for pede job to log folder(needs argument used for pedeStep.sh)
def writePedeSubmit(run,HG_bool,dirname):
    with open(dirname+"/submit_pede.sub","w") as f:
        f.write("""
Universe   = vanilla
Executable = pedeStep.sh
Arguments  = {0} {1}
Log        = {2}/log_pede.log
Output     = {2}/out_pede.out
Error      = {2}/error_pede.error
+JobFlavour = "microcentury"
+AccountingGroup = "group_u_CMS.CAF.ALCA"
Queue
""".format(run,HG_bool,dirname))
    return dirname+"/submit_pede.sub"

# method to write dag submit for single run
def writeDag(dirname):
    dirList=os.listdir(dirname)
    dag=""
    for dir in dirList:
        if "lumi" in dir:
            dag+="JOB mille_"+dir+" "+dirname+"/"+dir+"/submit_mille.sub\n"     # declare mille jobs
    dag+= "JOB pedeStep "+dirname+"/submit_pede.sub\n"      # declare pede job
    dag+="PARENT"
    for dir in dirList:
        if "lumi" in dir:
            dag+=" mille_"+dir
    dag+=" CHILD pedeStep"      # set pede job as child of mille jobs
    
    with open(dirname+"/dag_submit.dag","w") as f:
        f.write(dag)
    return "dag_submit.dag"

# method to write dag submit for several runs (running iteratively) Takes log folder as input, which has submits for mille and pede inside
def writeDag_Trend(dirname):
    dirList=sorted(os.listdir(dirname))
    dag=""
    firstRun=True       # check if run is first run of submit
    pedeStep_before=""
    for dir_run in dirList:
        if "run" not in dir_run: continue
        for dir_lumi in os.listdir(dirname+"/"+dir_run):
            if "lumi" in dir_lumi:
                dag+="JOB mille_"+dir_run+"_"+dir_lumi+" "+dirname+"/"+dir_run+"/"+dir_lumi+"/submit_mille.sub\n"
        dag+= "JOB pedeStep_"+dir_run+" "+dirname+"/"+dir_run+"/submit_pede.sub\n"
        if firstRun==False:     # if runs is not first run, the corresponding jobs have to wait for the previous run to finish
            dag+=pedeStep_before
            for dir_lumi in os.listdir(dirname+"/"+dir_run):
                if "lumi" in dir_lumi:
                    dag+=" mille_"+dir_run+"_"+dir_lumi
        dag+="\nPARENT"
        for dir_lumi in os.listdir(dirname+"/"+dir_run):
            if "lumi" in dir_lumi:
                dag+=" mille_"+dir_run+"_"+dir_lumi
        dag+=" CHILD pedeStep_"+dir_run+"\n\n"
        pedeStep_before="PARENT pedeStep_"+dir_run+" CHILD"
        firstRun=False
    
    with open(dirname+"/dag_submit.dag","w") as f:
        f.write(dag)
    return "dag_submit.dag"
    


def submitRun(run,HG_bool,LumisMax,LumisPerJob,StartLumi,SingleRun=True):
    print "Submitting run",run
    fileDict=getFileList_run(run)
    if len(fileDict)>100:       # use only runs with at least 100 lumi sections
        
        LumisMax=min(max(fileDict.keys()),LumisMax)     # set maximal number of lumis to set value or maximum available lumis
        
        cleanOutputFolder(run,HG_bool,True)     # clean output folder in case some run before fails
        
        for lumi in range(StartLumi,LumisMax+StartLumi,LumisPerJob):    # create run and log folder for each mille job and write config and submit
            dirname_log=createLogFolder(run,lumi,HG_bool)
            dirname_run=createRunFolder(run,lumi,HG_bool)
            fileList=getFileList_job(fileDict,lumi,LumisPerJob)
            
            writeMilleConfig(run,HG_bool,lumi,LumisPerJob,fileList,dirname_run)
            
            writeMilleSubmit(run,HG_bool,lumi,fileList,dirname_log)
    
        dirname_totalRun=os.path.dirname(dirname_log)
        writePedeSubmit(run,HG_bool,dirname_totalRun)       # write pede submit (not config needed since cmsDriver.py is used in pedeStep.sh)
        if SingleRun:   # single runs are currently submitted right away
            dugSubmit=writeDag(dirname_totalRun)
            subprocess.call(["condor_submit_dag", "-f", dirname_totalRun+"/"+dugSubmit])
        return True
    else:
        print "Not enough LumiSections"
        return False

print "!!!!!!Check if correct SG is loaded in the beginning and if study can be iterative (payloads already in output folder)!!!!!!!!"

#########################2018B long range with template update#################################
# set jsons for nominal and lowPU runs
url = "https://test-eos-cms-service-dqm.web.cern.ch/test-eos-cms-service-dqm/CAF/certification/Collisions18/13TeV/DCSOnly/json_DCSONLY.txt"
url_lowPU = "https://test-eos-cms-service-dqm.web.cern.ch/test-eos-cms-service-dqm/CAF/certification/Collisions18/13TeV/PromptReco/Cert_318939-319488_13TeV_PromptReco_SpecialCollisions18_JSON_LOWPU.txt"

# open url
response = urllib.urlopen(url)
response_lowPU = urllib.urlopen(url_lowPU)

# read json (and merge with lowPU)
data = json.loads(response.read())
data_lowPU = json.loads(response_lowPU.read())
#  ~data = merge_two_dicts(data,data_lowPU)

# get ordered dictionary with {run:"lumiRange1, lumiRange2"}
data = collections.OrderedDict(sorted(data.items()))

# define run range (different eras are usually run in different dag jobs)
#Run2018B
startingRun=317087
#  ~stoppingRun=318877
stoppingRun=317090
#Run2018C
#  ~startingRun=319337
#  ~stoppingRun=320065
#Run2018D partly
#  ~startingRun=320500
#  ~stoppingRun=321177

#Across Run2018B and Run2018C (used for lowPU included study)
#  ~startingRun=317626
#  ~stoppingRun=319699

# set helper variables
longestRange=0
totalLS=0
startLongestRange=0

# define the number of lumi sections to be used per run
numberOfLS=100

# loop over each run in the selected range
for run in data:
    if int(run)>=startingRun and int(run)<stoppingRun:
        for lsRange in data[run]:   # loop to find the longest range of lumis and store its length
            if lsRange[1]-lsRange[0]>longestRange: 
                longestRange=lsRange[1]-lsRange[0]
                startLongestRange=lsRange[0]
            totalLS+=lsRange[1]-lsRange[0]
        if longestRange>100:    # use run only if there is a lumi range with more an 100 LS
            if startLongestRange<20:startLongestRange=20    # do not use the first 100 Lumis
            #  ~submitRun(run,0,numberOfLS,5,startLongestRange,False)   # prepare LG with 5 lumis per mille job
            submitRun(run,1,numberOfLS,5,startLongestRange,False)   #prepare HG with 5 lumis per mille job
        longestRange=0      # set variables to zero for next run
        totalLS=0

# write dag submits for trends
writeDag_Trend("/afs/cern.ch/user/d/dmeuser/alignment/PCL/condor_PCL_2018/logs")
#  ~writeDag_Trend("/afs/cern.ch/user/d/dmeuser/alignment/PCL/condor_PCL_2018/logs_LG")

#Getting payload for UL: conddb_import -f frontier://FrontierProd/CMS_CONDITIONS -i TrackerAlignment_v28_offline -c sqlite:file.db -b 317626 -e 317626 -t SiPixelAli_pcl
#Getting payload for PR: conddb_import -f frontier://FrontierProd/CMS_CONDITIONS -i TrackerAlignment_PCL_byRun_v2_express -c sqlite:file.db -b 317080 -e 317080 -t SiPixelAli_pcl

#load t0 setting: module load lxbatch/tzero
