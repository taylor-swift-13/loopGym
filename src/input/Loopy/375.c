// Source: data/benchmarks/sv-benchmarks/loop-lit/gj2007b.c
extern int unknown_int(void);

void loopy_375(int n) {
    int x = 0;
    int m = 0;
    
    while(x < n) {
	if(unknown_int()) {
	    m = x;
	}
	x = x + 1;
    }
    {;
//@ assert((m >= 0 || n <= 0));
}

    {;
//@ assert((m < n || n <= 0));
}

    return;
}