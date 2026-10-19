**Versioning Issue**. 

The tags v0.9.9 and v0.9.10 were mistakenly created after v0.10.0 and point to commits containing code newer than v0.10.0. These tags are incorrectly versioned and should not be used as reliable indicators of release chronology.

Future releases will continue from v0.10.3 to avoid reusing version numbers associated with this incident.  

---

### Turin Routing System

The Turin routing system is the one utilized by turinflow.com.br. Utilize the “turin_build/osm14.py” with your PBF file to generate routing graphs.   

To assimilate our routing APIs, utilze our prebuilt containers or build your own with the provided components here. The most recent API server is b4.py.   

*Note: To host routing APIs without the authentication, you must either: fork our application, or use any version predating v0.10.0 (except v0.9.9 and v0.9.10).*

We **DO NOT** offer warranty nor support of any nature, and the software provided is both open source and "as-is". You are free to fork it. 

Data is provided under the ODbL 1.0 License, and you are free to use the data, provided adequate attribution to OSM and/or the OpenStreetMap Foundation (OSMF). 
