// Source: data/benchmarks/LinearArbitrary-SeaHorn/VeriMAP/TRACER-testloop2_VeriMAP_true.c

void errorFn() {ERROR: goto ERROR;}
void loopy_21(int NONDET, int i, int N, int a){

  
  
  
  int x;

  if (NONDET > 0) x=1; else x=2;

  while (i<N){
    i=i+1;
  }

  {;
//@ assert(!( x >2 ));
}

return;

}