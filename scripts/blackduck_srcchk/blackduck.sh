#!/bin/bash
if [ -e package-meta-data ]; then
   echo "re-sync package-meta-data with umd-repo.jf.intel.com? [y/n]"
   read yesorno
else yesorno="Y"
fi

echo "re-do code scan even if blackduck.xml exists? [y/n]"
read redo

if [ "$yesorno" == "Y" -o "$yesorno" == "y" ]; then
   rm -rf package-meta-data
   git clone http://umd-repo.jf.intel.com/git/FC6/package-meta-data.git ./package-meta-data
fi
echo "Enter your account on jfipsca01.intel.com:"
read username
echo "Enter your password for the account:"
read password
echo "Start to login JF ProtexIP server..."
bdstool --server jfipscn01.intel.com --user $username  --password $password login
echo "Getting current projects..."
prjlist=`bdstool list-projects | sed -ne "/^c_.*/p"`
echo "$prjlist"
cd package-meta-data
echo "$prjlist" |
while read row; do
    echo Processing $row
    prjid=${row% *}
    echo Project $prjid
# remove leading space   
    gitid=`echo -n ${row#* }`
    gitid=${gitid#mid-}
    echo Git "$gitid"
    gitfolder=$(find ./ -name "$gitid" -type d | tail -n 1)
    #gitfolder=${gitfolder%/*/*}
    gitfolder=${gitfolder#*/}
    if [ -z "$gitfolder" ]; then
       echo no git folder
       continue;
    fi
    echo Git folder is $gitfolder    
    if [ ! -e $gitfolder/info/pristine_tip ]; then
       echo no pristine_tip will skip
       continue;
    fi
    if [ -e ../scancodes/$gitfolder/blackduck.xml ]; then
       echo already blackducked
       keepold=1
       if [ "$redo" == "n" -o "$redo" == "N" ]; then
          continue
       fi
       echo "will do re-scan as specified"
    else keepold=0
    fi
    if [ $keepold -eq 0 ]; then
       echo will do rm old scancodes folder
       rm -rf ../scancodes/$gitfolder
    fi
    mkdir -p ../scancodes/$gitfolder
    pristine_index=`cat $gitfolder/info/pristine_tip`
    echo pristine_index is $pristine_index
    git diff $pristine_index HEAD $gitfolder > ../scancodes/$gitfolder/src.c
    echo "removing leading +,++,+-"
    sed -ne "s/^[+-]*\(*\)*/\1/p" -i ../scancodes/$gitfolder/src.c
    cd ../scancodes/$gitfolder
    pwd
    echo bdstool start _________________________________________
    if [ $keepold -eq 0 ]; then
       bdstool new-project $prjid
    else bdstool reset-analysis
    fi
    bdstool analyze
    bdstool upload
    echo bdstool end __________________________________________
    cd -
done

