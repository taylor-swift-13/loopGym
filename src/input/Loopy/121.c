// Source: data/benchmarks/LinearArbitrary-SeaHorn/pie/hola/07.c

extern int unknown1 ();
extern int unknown2 ();

void loopy_121(int n) {
  int i, a, b;
  i = 0; a = 0; b = 0;

  if (n >= 0) {
  	while( i < n ) {
    		if(unknown2()) {
      			a = a+1;
      			b = b+2;
    		} else {
      			a = a+2;
      			b = b+1;
    		}
    		i = i+1;
  	}
  	{;
//@ assert( a+b == 3*n );
}

  }

  return;
}