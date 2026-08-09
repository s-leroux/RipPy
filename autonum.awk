BEGIN {
    FS = "|"
    OFS=" | "
    EP=1
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
	while (SEASON "x" EP in EPS) {
	    ++EP;
	}
	$4=sprintf("%dx%02d", SEASON, EP);
	EPS[SEASON "x" EP]=1
    } else {
    	EPNUM = $4
        LOCAL_SEASON = SEASON
        LOCAL_EPNUM = EP
        while (match(EPNUM, /([0-9]+)?x([0-9]+)/, GROUPS)) {
            if (GROUPS[1] != "") LOCAL_SEASON = (0 + GROUPS[1])
            if (GROUPS[2] != "") LOCAL_EPNUM = (0 + GROUPS[2])
            EPISODE = LOCAL_SEASON "x" LOCAL_EPNUM
	    EPS[EPISODE]=1;
	    EPNUM=substr(EPNUM, RSTART+RLENGTH);
	}
    }

    print
    next
}

{ print }
