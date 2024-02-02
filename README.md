
# DQM^2 Mirror

> **Note**
> More up-to-date information can be found in the [Wiki](./wiki)

This is a system to grab the information about DQM jobs from DQM^2 site,
parse it, removing sensitive information, and show selections outside the P5 are.

The architecture is sequential:

* `grabber.py` - Runs in the background, fetching information from each FU and BU machine.
* `server.py` - Simple server to serve the front-end, including the Control Room.  
* `dqmsquare_cfg.py` - Called from both `grabber` and `server`, it loads environment settings and creates a configuration object, which is used by the application. See [`.env_sample`](./.env_sample_production) for available settings.

The work is periodic: `grabber.py` retrieves information for each machine specified in `FFF_PLAYBACK_MACHINES` or `FFF_PRODUCTION_MACHINES` (depending on the arguments the grabber is launched with) through the `SERVER_FFF_MACHINE`, storing it into the database. 

Other scripts/files:

* `dqmsquare_deploy.sh` - to download some extra software and run PyInstaller. We are using PyInstaller to pack python together with extra libraries (not a firefox!) into single executable ignoring lack of the software at P5 machines.
* `services/dqmsquare_mirror@.service` - configuration of daemons for DQM^2 Mirror services
* `services/dqmsquare_mirror_wrapper.sh` - used in order to define the working folder and execute dqmsquare_robber, dqmsquare_parser or dqmsquare_server

Folders:

* `log` - folder to put logs files
* `tmp` - folder to put output from dqmsquare_robber and dqmsquare_parser

## Deployment

### Docker image on kubernetes, Python 3.11

We are using the CMSWEB kubernetes clusters to host our Docker container, which runs:

* The web server, and
* the two grabbers (one for production data, one for playback data).

The server is available to the Internet through the CMSWEB's frontend proxy. The grabber is also connected to P5 through the CMSWEB frontend proxy.
CMSWEB frontend requires by default authentication using a CERN grid certificate, so we are using one provided by CMSWEB team to k8 cluster.
The connection at P5 to DQM^2 is closed without authentication cookie defined in DQM^2 backend (`fff_web.py`).
Environment variable values are attached to the k8s cluster using an Opaque Secret defined in the `k8_secret.yaml` file.
To store `log` and `tmp`, we mount CephFS. The claim for CephFS is defined in `k8_claim_testbed.yaml` for the testbed cluster. In production and preproduction cluster, the CephFS volume is created by the cmsweb team.
Also, they requested that the Docker image created does not use the `root` user. The Docker source image is `python:3.11`.

1. `cd dqmsquare_mirror; docker build -t registry.cern.ch/cmsweb/dqmsquare_mirror:<tag> .` 
2. `docker login registry.cern.ch`
3. `docker push registry.cern.ch/cmsweb/dqmsquare_mirror:<tag>`

#### For the testbed cmsweb k8 cluster:

* Update the k8 config yaml (`k8_config_testbed.yaml`) to use `registry.cern.ch/cmsweb/dqmsquare_mirror:v1.1.0`
* Log into `lxplus8` and run:

```bash
  export KUBECONFIG=/afs/cern.ch/user/m/mimran/public/cmsweb-k8s/config.cmsweb-test4
  kubectl apply -f k8_claim_testbed.yaml # (Only needed if this PVC has not been applied yet)
  kubectl apply -f k8_config_testbed.yaml
```

to login into a pod:

```bash
  kubectl get pods -n dqm
  # find the pod name which looks like dqm-square-mirror-server-<something> 
  kubectl exec <pod name> -it -n dqm -- bash
```

While Service claim with port definition is avalable in testbed yaml maifest file, it is not supported by cmsweb (TODO: what does that mean?).

Deployment to the production cmsweb is similar, see:
https://cms-http-group.docs.cern.ch/k8s_cluster/cmsweb_production_cluster_doc/

## DQM^2 Mirror Control Room (CR)

CR is a place to simplify the operations of DQM services. It send requests to DQM^2 on one of the playback machine at P5 where requests are executed.
Secrets and versions of DQM^2 need to match DQM^2 Mirror requirements, please check for more info https://github.com/cms-DQM/fff_dqmtools

### Scripts

1. `dqmsquare_cert.sh` imports `.pem` certificates provided by cmsweb k8 cluster into `.p12` format and then into NSS sql DB used by firefox without master password.

### Useful extras

* `bottle`'s built-in default server is not for a heavy server load, just for 3-5 shifters
* Number of logs created by `dqmsquare_robber.py`/`dqmsquare_robber_oldruns.py`/`dqmsquare_parser.py`/`dqmsquare_server.py`/`dqmsquare_server_flash.py` is limited by `TimedRotatingFileHandler`
* `dqmsquare_robber.py` spawns lot of firefox subprocesses. In case of the `dqmsquare_robber.py` process is killed they may persist, requiring the manual killing to free the resources.
* To build:
 `./dqmsquare_deploy.sh build`
* at p5 for installation, for example  
  `sudo rpm -e dqmsquare_mirror; sudo rpm -i /nfshome0/pmandrik/dqmsquare_mirror-1.0.0-1.x86_64.rpm`
