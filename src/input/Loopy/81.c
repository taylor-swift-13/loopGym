// Source: data/benchmarks/LinearArbitrary-SeaHorn/pie/ICE/benchmarks/cegar2.c
extern int unknown_int(void);

void loopy_81(int N, int input) {

	
	int x = 0;
	int m = 0;
	

 	while (x < N) {

		input = unknown_int();
		if( input ) {

			m = x;
		}

		x = x + 1;

	}

	if (N > 0) {
		{;
//@ assert((0 <= m) && (m < N));
}

	}

}