// Source: data/benchmarks/LinearArbitrary-SeaHorn/VeriMAP/TRACER-testabs8_VeriMAP_true.c

void errorFn() {ERROR: goto ERROR;}
void loopy_11(int n){
  int i;

  i=0;n=10;

  while (i < n){ i++; }

  {;
//@ assert(!( i>10 ));
}

}