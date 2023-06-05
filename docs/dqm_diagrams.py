# Petr~S.~Mandrik, 2021, IHEP, https://github.com/pmandrik

from diagrams import Cluster, Diagram, Edge
from diagrams.programming.flowchart import InputOutput as nIO
from diagrams.programming.flowchart import Action      as nA
from diagrams.programming.flowchart import StartEnd    as nSE
from diagrams.programming.flowchart import MultipleDocuments as nMD
from diagrams.programming.flowchart import OffPageConnectorLeft as nL
from diagrams.programming.flowchart import OffPageConnectorRight as nR

graph_attr = {"fontsize": "45"}
node_attr  = {"fontsize": "10"}

def hltd_fu():
  with Diagram("HLTD FU Machines", show=False, graph_attr=graph_attr, node_attr=node_attr, outformat="pdf"):
    with Cluster("HLT daemon service                   ", graph_attr={"bgcolor":"#EBF3E7"}):
      demon = nSE("/usr/lib/systemd/system/hltd.service")

    with Cluster("/opt/hltd/scratch/python/hltd.py"):
      hltd = nA("cleanup /fff/data\nlink /opt/hltd/cgi  to  /fff/data/cgi-bin\nstart http server port 9000\ncreate ResInfo()")

    with Cluster("/opt/hltd/scratch/python/HLTDInfo.py"): 
      ResInfo = nA("interface to work with Clients statuses\n/etc/appliance/dqm_resources/*\nstatuses: idle, cloud, except, quarantined")
      
    with Cluster("/opt/hltd/scratch/python/SystemMonitor.py"):
      SystemMonitor = nA("SystemMonitor.run()\n send info about fu machine") 
      
    boxes = nL("/fff/BU0/ramdisk/appliance/boxes/")

    with Cluster("/opt/hltd/python/ResourceRanger.py            "):
      resr = nA("watch clients /etc/appliance/dqm_resources/*\n Run.StartOnResource() when find indle clients")

    with Cluster("/opt/hltd/python/RunRanger.py"):
      runr = nA("watch /fff/data\n for new run:\n create Run(...)\ncall Run.Start()")

    with Cluster("/opt/hltd/python/inotifywrapper.py", graph_attr={"bgcolor":"#ECE8F6"}):
      inotify = nA("inotify wrapper")

    with Cluster("/opt/hltd/python/Run.py                          "):
      run = nA("Run.__init__(): create anelasticDQM() \n Run.Start() -> Run.StartOnResource() -> \n -> OnlineResource.StartNewProcess()")

    with Cluster("/opt/hltd/python/Resource.py | OnlineResource", graph_attr={"bgcolor":"#EBF3E7"}):
      res = nMD("StartNewProcess():\n parse run .global files\n create ProcessWatchdog()\n Popen(startRun.sh)")

    with Cluster("/opt/hltd/python/Resource.py | ProcessWatchdog", graph_attr={"bgcolor":"#EBF3E7"}):
      wdog = nMD("wait return code from startRun.sh\ncrash -> restart, OnlineResource.moveUsedToBroken()\ncan't restart -> OnlineResource.moveUsedToQuarantined()\nsuccess -> OnlineResource.moveUsedToIdles()")

    with Cluster("/opt/hltd/python/startRun.sh", graph_attr={"bgcolor":"#EBF3E7"}):
      srun = nMD("execute cmsRun")

    with Cluster("/opt/hltd/python/anelasticDQM.py", graph_attr={"bgcolor":"#FDF7E3"}):
      anel = nA("create DQMFileWatcherFU(runNumber)\nwatch /home/dqmdevlocal/output/upload/\nrename and they move to a BU.")

    psutil = nR("psutil")
    bu = nL("BU machine \n /fff/BU0/output/DQMOutput")

    clients = nL("Clients: /etc/appliance/dqm_resources/*")

    guiold = nR("DQM GUI OLD")
    outfolder = nR("/home/dqmdevlocal/output/upload/\n/home/dqmprolocal/output/upload/")
    

    demon >> hltd
    hltd >> resr
    hltd >> runr
    hltd >> ResInfo
    hltd >> SystemMonitor >> boxes

    resr << Edge(color="darkgreen") >> ResInfo
    ResInfo << Edge(color="darkgreen") >> clients

    resr - Edge(color="brown", style="dashed") - inotify
    runr - Edge(color="brown", style="dashed") - inotify
    anel - Edge(color="brown", style="dashed") - inotify

    runr >> run >> res >> srun
    res << Edge(color="darkgreen") >> wdog
    res << Edge(color="darkgreen") >> ResInfo

    # srun >> Edge(label="exitcode") >> wdog  
    srun >> wdog  
    srun >> guiold
    resr >> run
    run  >> anel >> bu
    psutil >> anel 
    run  << Edge(color="darkgreen") >> ResInfo
    srun >> outfolder >> anel

def hltd_bu():
  with Diagram("HLTD BU Machines", show=False, graph_attr=graph_attr, node_attr=node_attr, outformat="pdf"):
    with Cluster("HLT daemon service                   ", graph_attr={"bgcolor":"#EBF3E7"}):
      demon = nSE("/usr/lib/systemd/system/hltd.service")

    # '/fff/ramdisk'
    with Cluster("/opt/hltd/scratch/python/hltd.py            "):
      hltd = nA("MountManager()\nMountManager.submount_size('/fff/ramdisk')\nSystemMonitor()\nResourceRanger()") 
      
    with Cluster("/opt/hltd/scratch/python/SystemMonitor.py"):
      SystemMonitor = nA("") 

    with Cluster("/opt/hltd/python/ResourceRanger.py            "):
      ResourceRanger = nA("watch /fff/ramdisk/appliance/boxes/\n watch /etc/appliance/dqm_resources/ \n IN_CREATE call findRunAndNotify()->\n->Resource.NotifyNewRun()->\n->Notify FU to start a run, HTTPConnection")

    with Cluster("/opt/hltd/python/RunRanger.py"):
      RunRanger = nA("watch /fff/data\n for new run:\n cleanupBUCmd(...)\ncreate Run(...)\nRun.AcquireResources()\nRun.Start()")
      
    with Cluster("/opt/hltd/python/Run.py                          "):
      run = nA("Run.__init__(): create anelasticDQM() \n Run.Start() -> Run.StartOnResource() -> \n -> OnlineResource.StartNewProcess()")

    with Cluster("/opt/hltd/python/inotifywrapper.py", graph_attr={"bgcolor":"#ECE8F6"}):
      inotify = nA("inotify wrapper")
      
    with Cluster("/opt/hltd/python/anelasticDQM.py", graph_attr={"bgcolor":"#FDF7E3"}):
      anel = nA("create DQMFileWatcherBU(runNumber)\n watch /fff/output/DQMOutput \n watch /fff/ramdisk/appliance/boxes/\n if all heartbeat files older 1m -> \n -> run is over")
      
    bu = nL("FU machine \n /fff/output/DQMOutput")
    boxes = nL("/fff/BU0/ramdisk/appliance/boxes/")
    
    demon >> hltd
    hltd >> ResourceRanger
    hltd >> RunRanger
    bu >> anel
    hltd >> SystemMonitor >> boxes >> anel

    ResourceRanger - Edge(color="brown", style="dashed") - inotify
    RunRanger - Edge(color="brown", style="dashed") - inotify
    RunRanger >> run >> anel
    anel - Edge(color="brown", style="dashed") - inotify
    
  
hltd_fu()
hltd_bu()
  
