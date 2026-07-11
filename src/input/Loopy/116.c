// Source: data/benchmarks/LinearArbitrary-SeaHorn/pie/ICE/benchmarks/w2.c
extern int unknown_int(void);

/*@
  requires !(n <= 0);
*/
void loopy_116(int n, int input) {

	
	

	int x = 0;
	

 	while ( 0 == 0 ) {
		if ( input ) {

			x = x + 1;
			if (x >= n ) {
				break;
			}
		}
		input = unknown_int();
	}
	{;
//@ assert(x == n);
}

}