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
    	while (match(EPNUM, /([0-9]+)x([0-9]+)/, GROUPS)) {
            EPISODE=(0 + GROUPS[1]) "x" (0 + GROUPS[2])
	    EPS[EPISODE]=1;
	    EPNUM=substr(EPNUM, RSTART+RLENGTH);
	}
    }

    print
    next
}

{ print }
