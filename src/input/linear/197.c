int unknown();
/*@ requires k == x + y; */
void foo197(int k, int x, int y) {

    int i;
    int j;
    int m;
    int n;

    m = 0;
    j = 0;


        n = unknown();

    while(j < n){
       if(unknown()){
       m = j;
      }
       if(j == i){
       x = x + 1;
       y = y - 1;
      }
       else{
       x = x - 1;
       y = y + 1;
      }
       j = j + 1;
      }

    /*@ assert (n > 0) ==> (m >= 0); */

  }