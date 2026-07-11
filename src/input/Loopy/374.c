// Source: data/benchmarks/sv-benchmarks/loop-lit/gj2007.c

void loopy_374(void) {
    int x = 0;
    int y = 50;
    while(x < 100) {
	if (x < 50) {
	    x = x + 1;
	} else {
	    x = x + 1;
	    y = y + 1;
	}
    }
    {;
//@ assert(y == 100);
}

    return;
}