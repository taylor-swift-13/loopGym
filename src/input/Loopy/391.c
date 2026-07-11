// Source: data/benchmarks/sv-benchmarks/loop-zilu/benchmark03_linear.c
extern int unknown_int(void);
extern int unknown_bool(void);
/*@
  requires i==0 && j==0;
  requires (flag == 0 || flag == 1);
*/
void loopy_391(int i, int j, int flag) {
  int x = unknown_int();
  int y = unknown_int();
  
  
  
  
  x = 0; y = 0;
  
  while (unknown_bool()) {
    x++;
    y++;
    i+=x;
    j+=y;
    if (flag) j+=1;
  }
  {;
//@ assert(j>=i);
}

  return;
}