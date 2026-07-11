// Source: data/benchmarks/LinearArbitrary-SeaHorn/VeriMAP/TRACER-testloop17_VeriMAP_true.c
extern unsigned int unknown_uint(void);

;

void errorFn() {ERROR: goto ERROR;}
/*@
  requires N > 1;
*/
void loopy_18(int N)
{
	
  int i, j, k;

  i = 0;
  j = 0;
  k = 0;

  

  while (i < N) {
    if (i<1)
      k = 1;
    else
      k = 0;
    j++;
    i++;
  }

  {;
//@ assert(!( k>0 ));
}

  return;
}