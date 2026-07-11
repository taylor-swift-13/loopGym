// Source: data/benchmarks/sv-benchmarks/loops/sum01-2.c
extern int unknown_int(void);
#define a (2)

/*@
  requires n < 1000 && n >= -1000;
*/
void loopy_462(int i, int n) { 
  int sn=0;
  
  {
  i=1;
  while (i<=n) {
    sn = sn + a;
    i++;
  }
}
  {;
//@ assert(sn==n*a || sn == 0);
}

}