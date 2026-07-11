// Source: data/benchmarks/LinearArbitrary-SeaHorn/VeriMAP/TRACER-testloop6_VeriMAP_true.c
extern unsigned int unknown_uint(void);

;

void errorFn() {ERROR: goto ERROR;}
/*@
  requires y>=0;
*/
void loopy_23(int y, int NONDET)
{
  int i, x, z;

  x=0;
  z=1;

  
  i = 0;
  while (i < 10) {
    if (NONDET > 0) {
      x = x;
    } else {
      x++;
    }

    {;
//@ assert(!( y < 0 ));
}

    i++;
  }
  {;
//@ assert(!( z<0 ));
}

}