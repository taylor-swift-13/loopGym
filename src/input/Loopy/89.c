// Source: data/benchmarks/LinearArbitrary-SeaHorn/pie/ICE/benchmarks/fig3.c
extern int unknown_int(void);

void loopy_89(int y, int x, int input) {

	
	int lock;
	lock = 0;
	
	

	{
		lock = 1;
		x = y;
		if( input ) {

			lock = 0;
			y = y + 1;
		}
	}

	while(x != y) {

		lock = 1;
		x = y;
		input = unknown_int();
		if ( input ) {

			lock = 0;
			y = y + 1;
		}
	}

	{;
//@ assert(lock == 1);
}

}
