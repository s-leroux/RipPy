BEGIN {
    FS = "|"
    OFS=" | "
    EP=0
    SEASON=1
    TITLE=""
    EPS[0]=1
}

/^[@#]/ {
    print
    next
}

NF == 5 {
    if(TITLE)
        $1=TITLE
    if ($4 == 2000) {
	while (EP in EPS) {
	    ++EP;
	}
	$4=sprintf("%dx%02d", SEASON, EP);
	EPS[EP]=1
    } else {
    	EPNUM = $4
    	while (match(EPNUM, /x[0-9]+/)) {
	    EPS[0+substr(EPNUM, RSTART+1, RLENGTH-1)]=1;
	    EPNUM=substr(EPNUM, RSTART+RLENGTH);
	}
    }

    print
    next
}

{ print }
