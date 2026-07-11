// Source: data/benchmarks/LinearArbitrary-SeaHorn/pie/ICE/benchmarks/cggmp2005_true-unreach-call.c

void loopy_83(void) {
    int i, j;
    i = 1;
    j = 10;
    while (j >= i) {
	i = i + 2;
	j = -1 + j;
    }
    {;
//@ assert(j == 6);
}

}