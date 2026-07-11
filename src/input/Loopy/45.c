// Source: data/benchmarks/LinearArbitrary-SeaHorn/llreve/fib_merged_safe.c
extern int unknown(void);

void loopy_45(int n) {
	
  int f1 = 0;   
  int f2 = 1;  
  int g1 = 1, g2 = 1;
  int h1 = 0, h2 = 0;

  while((n > 0)) {
    h1 = f1 + g1;
    f1 = g1;
    g1 = h1;
    n --;

    h2 = f2 + g2;
    f2 = g2;
    g2 = h2;

	{;
//@ assert(h2==h1+f1);
}

  }
}